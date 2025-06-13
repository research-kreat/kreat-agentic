from neo4j import GraphDatabase
import os
import requests
import re
import json
import concurrent.futures
import time
import logging
from pymongo import MongoClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import functools
from helpers.custom_logger import print_start_time, print_end_time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize connections as global variables to avoid repeated connections
neo4j_driver = None
mongo_client = None
db = None

# Cache for embeddings and processed text
embedding_cache = {}
processed_text_cache = {}

# Azure OpenAI config
azure_config = {
    'endpoint': os.getenv("AZURE_OPENAI_ENDPOINT"),
    'key': os.getenv("AZURE_OPENAI_API_KEY"),
    'version': os.getenv("AZURE_OPENAI_API_VERSION"),
    'deployment': os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
}

vector_index_name = "knowledge_embedding"

def initialize_connections():
    """Initialize database connections once"""
    global neo4j_driver, mongo_client, db
    
    if not neo4j_driver:
        neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"), 
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
            max_connection_lifetime=300  # 5 minutes
        )
    
    if not mongo_client:
        mongo_client = MongoClient(
            os.getenv("mongo_string"),
            maxPoolSize=10,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client["trends_test"]

def create_error_response(error_message, source_type):
    """Create standardized error response"""
    return [{"title": f"Error in {source_type}: {error_message}", "id": "error", "similarity_score": 0.0, 
             "error": True, "error_message": error_message, "source_db": source_type}]

@functools.lru_cache(maxsize=128)
def preprocess_text(text):
    """Preprocess text with caching for performance"""
    if text in processed_text_cache:
        return processed_text_cache[text]
    
    # Simple but fast preprocessing
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Basic stopword removal without NLTK dependency
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    tokens = text.split()
    result = ' '.join([word for word in tokens if word not in stop_words and len(word) > 2])
    
    processed_text_cache[text] = result
    return result

def get_embeddings(text, retry=1):
    """Get embeddings from Azure OpenAI with caching and retry logic"""
    if not all(azure_config.values()):
        return None
    
    # Check cache first
    if text in embedding_cache:
        return embedding_cache[text]
    
    # Implement timeout for embedding API calls
    timeout = min(5, 2 * retry)  # Increase timeout with retries, max 5 seconds
    
    try:
        response = requests.post(
            f"{azure_config['endpoint']}/openai/deployments/{azure_config['deployment']}/embeddings?api-version={azure_config['version']}",
            headers={"Content-Type": "application/json", "api-key": azure_config['key']},
            json={"input": text, "encoding_format": "float"},
            timeout=timeout
        )
        
        if response.status_code == 200:
            embedding = response.json()["data"][0]["embedding"]
            embedding_cache[text] = embedding
            return embedding
        elif retry > 0 and response.status_code >= 500:
            # Retry server errors with backoff
            time.sleep(0.5)
            return get_embeddings(text, retry - 1)
        else:
            return None
    except requests.exceptions.Timeout:
        if retry > 0:
            time.sleep(0.5)
            return get_embeddings(text, retry - 1)
        return None
    except Exception as e:
        logger.error(f"Embedding error: {str(e)}")
        return None

# Fix the function signatures to be consistent

def get_mongo_source(input, top_n=10, timeout=10):  # Add timeout parameter
    """Get MongoDB results with optimized query and projection"""
    try:
        initialize_connections()
        
        # Set a timeout for MongoDB operations
        start_time = time.time()
        max_time = timeout  # Use the passed timeout parameter
        
        processed_input = preprocess_text(input)
        
        # Use projection to only fetch needed fields
        projection = {
            "title": 1, 
            "abstract": 1, 
            "_id": 1,
            "publication_date": 1,
            "keywords": 1,
            "url": 1
        }
        
        # Run concurrent queries for collections
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            journals_future = executor.submit(list, db["journals"].find({}, projection).limit(50))
            patents_future = executor.submit(list, db["patents"].find({}, projection).limit(50))
            
            journals = journals_future.result()
            patents = patents_future.result()
            
        all_docs = journals + patents
        
        if not all_docs:
            return create_error_response("No documents found in MongoDB collections", "mongo_db")

        # Optimize by using list comprehension
        documents = []
        doc_texts = []
        
        for doc in all_docs:
            doc_text = f"{doc.get('title', '')} {doc.get('abstract', '')}".strip()
            if doc_text:
                documents.append(doc)
                doc_texts.append(preprocess_text(doc_text))
        
        if not doc_texts:
            return create_error_response("No valid document content found", "mongo_db")

        # Check time limit
        if time.time() - start_time > max_time:
            # Return partial results if timeout
            return [{"title": "MongoDB timeout", "error": True, "source_db": "mongo_db"}]

        # Use a lighter version of TF-IDF with fewer features
        vectorizer = TfidfVectorizer(stop_words='english', max_features=2000)
        tfidf_matrix = vectorizer.fit_transform([processed_input] + doc_texts)
        
        # Compute similarities and get top N
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        # Use numpy for faster ranking
        import numpy as np
        top_indices = np.argsort(similarities)[-top_n:][::-1]
        
        source = []
        for idx in top_indices:
            doc = documents[idx]
            doc_copy = dict(doc)
            doc_copy.update({
                "similarity": round(float(similarities[idx]), 3), 
                "source_db": "mongo_db", 
                "_id": str(doc_copy["_id"])
            })
            source.append(doc_copy)

        return source
    except Exception as e:
        logger.error(f"Error in get_mongo_source: {str(e)}")
        return create_error_response(str(e), "mongo_db")

def get_neo4j_source(input, top_n=10, timeout=10):
    """Get Neo4j results with optimized query and timeout"""
    try:
        initialize_connections()
        start_time = time.time()
        
        preprocessed_prompt = preprocess_text(input)
        query_embedding = get_embeddings(preprocessed_prompt)
        
        # Early termination if time is running out
        if time.time() - start_time > timeout * 0.7:
            return create_error_response("Time limit approaching, skipping Neo4j query", "neo4j_db")
        
        with neo4j_driver.session() as session:
            results = []
            
            # Optimized vector query with fewer path hops and limited returns
            if query_embedding:
                vector_query = """
                CALL db.index.vector.queryNodes($index_name, $num_neighbors, $embedding)
                YIELD node, score
                WITH node as k, score AS similarity_score
                
                // Match only essential connected entities
                OPTIONAL MATCH (k)-[:ASSIGNED_TO]->(assignee:Assignee)
                OPTIONAL MATCH (k)-[:WRITTEN_BY]->(author:Author)
                OPTIONAL MATCH (k)-[:HAS_KEYWORD]->(keyword:Keyword)
                OPTIONAL MATCH (k)-[:IN_SUBDOMAIN]->(subdomain:Subdomain)
                
                RETURN 
                    k.id AS id,
                    similarity_score,
                    k.title AS title,
                    k.domain AS domain,
                    k.knowledge_type AS knowledge_type,
                    k.publication_date AS publication_date,
                    k.country AS country,
                    k.data_quality_score AS data_quality_score,
                    COLLECT(DISTINCT assignee.name)[..5] AS assignees,
                    COLLECT(DISTINCT author.name)[..5] AS authors,
                    COLLECT(DISTINCT keyword.name)[..10] AS keywords,
                    COLLECT(DISTINCT subdomain.name)[..5] AS subdomains
                ORDER BY similarity_score DESC
                LIMIT $limit
                """
                
                try:
                    # Set query timeout
                    results = session.run(
                        vector_query, 
                        index_name=vector_index_name, 
                        num_neighbors=10, 
                        embedding=query_embedding, 
                        limit=int(top_n)
                    ).data()
                except Exception as e:
                    logger.error(f"Vector search failed: {str(e)}")
            
            # Early termination if time is running out
            if time.time() - start_time > timeout * 0.9:
                if results:
                    # Return whatever we have so far
                    logger.info("Time limit approaching, returning partial Neo4j results")
                else:
                    return create_error_response("Time limit exceeded, skipping fallback query", "neo4j_db")
            
            # Simplified fallback query if needed
            if not results:
                fallback_query = """
                MATCH (k:Knowledge)
                WHERE k.title IS NOT NULL
                
                WITH k ORDER BY k.data_quality_score DESC LIMIT 20
                
                OPTIONAL MATCH (k)-[:ASSIGNED_TO]->(assignee:Assignee)
                OPTIONAL MATCH (k)-[:HAS_KEYWORD]->(keyword:Keyword)
                
                RETURN 
                    COALESCE(k.id, toString(elementId(k))) AS id,
                    0.1 as similarity_score,
                    k.title AS title,
                    k.domain AS domain,
                    k.knowledge_type AS knowledge_type,
                    k.publication_date AS publication_date,
                    COLLECT(DISTINCT assignee.name)[..5] AS assignees,
                    COLLECT(DISTINCT keyword.name)[..10] AS keywords
                LIMIT $limit
                """
                
                try:
                    # Set query timeout
                    results = session.run(fallback_query, limit=int(top_n)).data()
                except Exception as e:
                    logger.error(f"Fallback query failed: {str(e)}")
                    return create_error_response(f"Both vector and fallback queries failed: {str(e)}", "neo4j_db")
            
            # Process results efficiently
            source = []
            for item in results:
                # Simplified result processing with fewer fields
                source_data = {
                    "title": item.get("title", "Unknown"),
                    "id": item.get("id", "Unknown"),
                    "similarity_score": item.get("similarity_score", 0.0),
                    "knowledge_type": item.get("knowledge_type", "Unknown"),
                    "domain": item.get("domain", "Unknown"),
                    "publication_date": item.get("publication_date", "Unknown"),
                    "assignees": item.get("assignees", []),
                    "keywords": item.get("keywords", []),
                    "source_db": "neo4j_db"
                }
                source.append(source_data)
            
            return source if source else create_error_response("No results found in Neo4j", "neo4j_db")
            
    except Exception as e:
        logger.error(f"Error in Neo4j processing: {str(e)}")
        return create_error_response(str(e), "neo4j_db")

# def get_web_search(input, top_n=5, timeout=5):
    # """Get web search results with timeout"""
    # try:
    #     start_time = time.time()
        
    #     # Simplified query preparation
    #     cleaned_input = re.sub(r'[^\w\s]', ' ', input)
    #     words = cleaned_input.strip().split()
    #     search_query = ' '.join(words[-10:] if len(words) > 10 else words)
        
    #     logger.info(f"Using search query: {search_query}")
        
    #     # Set a timeout for the search
    #     with concurrent.futures.ThreadPoolExecutor() as executor:
    #         future = executor.submit(DDGS().text, search_query, max_results=top_n)
            
    #         try:
    #             # Wait for completion or timeout
    #             search_results = list(future.result(timeout=timeout))
    #         except concurrent.futures.TimeoutError:
    #             logger.warning("Web search timed out")
    #             return [{"title": "Search timeout", "url": "", "summary": "Web search took too long"}]
        
    #     # Simplified source type detection
    #     source_types = {
    #         'academic': ['.edu', 'scholar.', 'sciencedirect'],
    #         'news': ['nytimes', 'cnn', 'bbc', 'reuters'],
    #         'government': ['.gov'],
    #         'blog': ['medium.com', 'wordpress']
    #     }
        
    #     results = []
    #     for result in search_results:
    #         url = result.get("href", "").lower()
    #         source_type = "web"
            
    #         for stype, keywords in source_types.items():
    #             if any(keyword in url for keyword in keywords):
    #                 source_type = stype
    #                 break
            
    #         results.append({
    #             "title": result.get("title", "No Title"),
    #             "url": result.get("href", ""),
    #             "summary": result.get("body", "No summary available"),
    #             "source_type": source_type
    #         })
            
    #     return results
        
    # except ImportError:
    #     return create_error_response("Required package not installed", "web_search")
    # except Exception as e:
    #     logger.error(f"Error in web search: {str(e)}")
    #     return create_error_response(str(e), "web_search")

def extract_strings_from_json(obj):
    """Extract string values from JSON more efficiently"""
    if not obj:
        return []
        
    strings = []
    
    # Handle dictionaries
    if isinstance(obj, dict):
        # Process values only
        for value in obj.values():
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, (dict, list)):
                strings.extend(extract_strings_from_json(value))
    
    # Handle lists
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str):
                strings.append(item)
            elif isinstance(item, (dict, list)):
                strings.extend(extract_strings_from_json(item))
    
    # Handle strings
    elif isinstance(obj, str):
        strings.append(obj)
        
    return strings

def retrieve_data_from_source(input, source_from="neo4j", overall_timeout=25):
    """Main function with overall timeout"""
    if source_from not in ("mongo", "neo4j"):
        return [], []
  
    try:
        # Start timing
        start_time = time.time()
        
        # Initialize connections early
        initialize_connections()
        
        # Extract and clean input
        idx = input.find('{')
        if idx > 0:
            text_part = input[:idx].strip()
            try:
                json_data = json.loads(input[idx:])
                string_values = extract_strings_from_json(json_data)
                clean_input = text_part + (' ' + ' '.join(string_values) if string_values else '')
            except json.JSONDecodeError:
                clean_input = text_part
        else:
            clean_input = input

        # Calculate timeouts for each operation
        elapsed = time.time() - start_time
        remaining_time = overall_timeout - elapsed
        
        db_timeout = min(10, remaining_time * 0.6)  # 60% of remaining time
        web_timeout = min(5, remaining_time * 0.3)  # 30% of remaining time
        
        # Run operations with individual timeouts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            source_future = executor.submit(
                get_mongo_source if source_from == "mongo" else get_neo4j_source, 
                clean_input, 
                10, 
                db_timeout
            )
            
            # web_future = executor.submit(
            #     get_web_search, 
            #     clean_input, 
            #     5,  # Reduced number of results
            #     web_timeout
            # )
            
            try:
                # Get results with timeouts
                source_start = print_start_time()
                
                # Calculate a timeout for this future
                elapsed = time.time() - start_time
                future_timeout = max(1, overall_timeout - elapsed - 2)  # -2 for safety margin
                
                source = source_future.result(timeout=future_timeout)
                print_end_time(source_start, "source_retrieval_" + source_from)
                
                # Recalculate remaining time
                elapsed = time.time() - start_time
                future_timeout = max(1, overall_timeout - elapsed - 1)
                
                web_search_start = print_start_time()
                # web_search = web_future.result(timeout=future_timeout)
                # Simulated web search results for demonstration
                # In a real scenario, you would uncomment the above line and use the web_future
                web_search = [
                {
                    "title": "PESTEL Analysis (Full Breakdown) | Career Principles",
                    "url": "https://www.careerprinciples.com/resources/pestel-analysis-what-it-is-and-example-applications",
                    "summary": "The structured approach of PESTEL will make it easier for management to pinpoint specific issues that make up a larger layer of complex problems. Example: A food delivery company is struggling to find delivery drivers as the cost of fuel and overall car ownership continues to rapidly increase.",
                    "source_type": "web"
                },
                {
                    "title": "What Is PESTLE Analysis: Guide and Examples - Xmind Blog",
                    "url": "https://xmind.app/blog/pestle-analysis/",
                    "summary": "What Is PESTLE Analysis? PESTLE Analysis is a framework used by businesses to analyze macro-environmental factors affecting their industry, strategy, and decision-making. It helps organizations anticipate risks, identify opportunities, and align their strategies with external conditions. Understanding the Six Factors Political - Examines government policies, regulations, tax laws, and ...",
                    "source_type": "web"
                },
                {
                    "title": "PESTEL Framework: The 6 Factors of PESTEL Analysis",
                    "url": "https://pestleanalysis.com/pestel-framework/",
                    "summary": "The PESTEL framework (political, economic, social, technological, environmental, legal) helps managers assess how external factors affect a business.",
                    "source_type": "web"
                },
                {
                    "title": "How to Conduct a PESTLE Analysis - Explained with Example",
                    "url": "https://upmetrics.co/blog/pestle-analysis",
                    "summary": "Learn how to conduct a PESTLE analysis to stay ahead of business risks and opportunities. Our guide provides step-by-step instructions and real-world examples.",
                    "source_type": "web"
                },
                {
                    "title": "PESTEL Analysis: Understanding the External Landscape - LinkedIn",
                    "url": "https://www.linkedin.com/pulse/pestel-analysis-understanding-external-landscape-gopal-sharma-fvjkc/",
                    "summary": "Learn how to use PESTEL analysis to understand external forces shaping your strategy — with tips, examples, and pitfalls to avoid.",
                    "source_type": "web"
                }
             ]
                print_end_time(web_search_start, "web_search_retrieval")
                
                logger.info(f"Retrieved {len(web_search)} web results and {len(source)} source items in {time.time() - start_time:.2f}s")
                
            except concurrent.futures.TimeoutError:
                logger.error(f"Timeout during concurrent execution")
                # Get partial results if available
                source = source_future.result(0.1) if source_future.done() else create_error_response("Timeout", source_from)
                # web_search = web_future.result(0.1) if web_future.done() else create_error_response("Timeout", "web_search")

            except Exception as e:
                logger.error(f"Error during concurrent execution: {str(e)}")
                source = create_error_response(f"Execution failed: {str(e)}", source_from)
                web_search = create_error_response(f"Execution failed: {str(e)}", "web_search")
                
        if time.time() - start_time > overall_timeout * 0.9:
            logger.warning(f"Approaching overall timeout, returning partial results")
                
        return source, web_search
    
    except Exception as e:
        logger.error(f"Error in retrive_data_from_source: {str(e)}")
        return create_error_response(str(e), source_from), create_error_response(str(e), "web_search")
    
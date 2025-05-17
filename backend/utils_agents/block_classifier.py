from crewai import Agent, Task, Crew, Process
from crewai import LLM
import logging
import json
import re

logger = logging.getLogger(__name__)

def classify_user_input(user_input):
    """
    Classifies the user input into one of the eight block types or identifies it as a greeting.
    
    Returns:
        tuple: (block_type, confidence_score, is_greeting, classification_message)
    """
    # First check if it's a greeting using a simple rule-based approach
    greeting_phrases = [
        "hi", "hello", "hey", "greetings", "good morning", "good afternoon", 
        "good evening", "howdy", "what's up", "how are you", "nice to meet you",
        "how's it going", "sup", "yo", "hiya", "hi there", "hello there",
        "hey there", "welcome", "good day", "how do you do"
    ]
    
    # Clean and normalize input for comparison
    clean_input = user_input.lower().strip()
    
    # Check if the input is just a simple greeting
    is_greeting = False
    for phrase in greeting_phrases:
        if clean_input.startswith(phrase) or clean_input == phrase:
            is_greeting = True
            break
    
    # If it's a simple greeting with no substantive content, return general type with low confidence
    if is_greeting and len(clean_input.split()) <= 5:
        return "general", 5, True, "Welcome to SparkBlocks. How can I help you today?"
    
    try:
        # Initialize LLM
        llm = LLM(
            model="azure/gpt-4o-mini", 
            temperature=0.2
        )
        
        # Create classification agent
        classification_agent = Agent(
            role="Conversation Analyst",
            goal="Understand what people are trying to discuss and provide appropriate classification messages",
            backstory="""You're good at understanding what topics people want to talk about and providing helpful classification messages. 
            When someone shares a thought, you can tell if they're talking about an idea, 
            a problem, a possibility, or something else.""",
            verbose=True,
            llm=llm
        )
        
        # Classification task
        classification_task = Task(
            description=f"""
            Read what this person has shared:
            
            "{user_input}"
            
            Figure out which of these categories fits best:
            - "idea" - They're sharing a creative concept or innovative solution
            - "problem" - They're describing an issue or challenge that needs solving
            - "possibility" - They're exploring a potential approach or solution
            - "moonshot" - They're proposing an ambitious, potentially transformative idea
            - "needs" - They're talking about requirements or necessities
            - "opportunity" - They're pointing out a favorable circumstance or chance
            - "concept" - They're outlining a structured solution or framework
            - "outcome" - They're discussing results or end states
            
            IMPORTANT: If they're just saying hello (like "hello", "hi", "hey there") with no real content,
            mark this as a greeting.
            
            Once you've determined the category, create a standardized classification message that follows this pattern:
            
            For problems:
            "Great! Let's classify this problem related to [brief topic]. This will help us understand it better. Once classified, we can decide on the next steps."
            
            For ideas:
            "Great! I've identified this as an idea related to [brief topic]. Let's explore it further. Once classified, we can proceed to generate a title that captures the essence of your idea!"
            
            For possibilities:
            "Great! Let's explore this possibility related to [brief topic]. This will help us understand its potential. Once classified, we can decide on the next steps."
            
            For moonshots:
            "Great! Let's classify this moonshot vision related to [brief topic]. This will help us understand its transformative potential. Once classified, we can decide on the next steps."
            
            For other types:
            "Great! I've identified this as a [type] related to [brief topic]. Let's explore it further. Once classified, we can decide on the next steps."
            
            Your output must be EXACTLY in this JSON format:
            {{
                "block_type": "one of the eight types listed above, or 'general' if it's just a greeting",
                "confidence": "a number between 1-10 representing your confidence",
                "is_greeting": "true or false - whether this is primarily just a greeting",
                "classification_message": "Your standardized classification message following the pattern above"
            }}
            """,
            agent=classification_agent,
            expected_output="Classification in the specified JSON format"
        )
        
        # Create crew with single agent and task
        crew = Crew(
            agents=[classification_agent],
            tasks=[classification_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Execute the classification
        result = crew.kickoff()
        
        # Parse the result
        json_match = re.search(r'({.*})', result.raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                result_data = json.loads(json_str)
                block_type = result_data.get("block_type", "problem")  # Default to problem if parsing fails
                confidence = int(result_data.get("confidence", 7))  # Default confidence
                is_greeting = result_data.get("is_greeting", "false").lower() == "true"
                classification_message = result_data.get("classification_message", "")
                
                # Add default classification message if not provided
                if not classification_message:
                    if is_greeting:
                        classification_message = "Welcome to SparkBlocks. How can I help you today?"
                    else:
                        classification_message = f"Great! I've identified this as a {block_type} type. Let's explore it further."
                
                return block_type, confidence, is_greeting, classification_message
            except json.JSONDecodeError:
                logger.error(f"Failed to parse classification result: {json_str}")
                return "problem", 5, False, "Let's classify this problem. This will help us understand it better. Once classified, we can decide on the next steps."
        else:
            logger.error("No JSON found in classification result")
            return "problem", 5, False, "Let's classify this problem. This will help us understand it better. Once classified, we can decide on the next steps."
            
    except Exception as e:
        logger.error(f"Error in classification: {str(e)}")
        return "problem", 5, False, "Let's classify this problem. This will help us understand it better. Once classified, we can decide on the next steps."
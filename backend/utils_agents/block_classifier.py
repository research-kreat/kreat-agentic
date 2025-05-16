from crewai import Agent, Task, Crew, Process
from crewai import LLM
import logging

logger = logging.getLogger(__name__)

def classify_user_input(user_input):
    """
    Classifies the user input into one of the eight block types or identifies it as a greeting.
    
    Returns:
        tuple: (block_type, confidence_score, is_greeting)
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
        return "general", 5, True
    
    try:
        # Initialize LLM
        llm = LLM(
            model="azure/gpt-4o-mini", 
            temperature=0.2
        )
        
        # Create classification agent
        classification_agent = Agent(
            role="Conversation Analyst",
            goal="Understand what people are trying to discuss",
            backstory="""You're good at understanding what topics people want to talk about. 
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
            
            Your output must be EXACTLY in this JSON format:
            {{
                "block_type": "one of the eight types listed above, or 'general' if it's just a greeting",
                "confidence": "a number between 1-10 representing your confidence",
                "is_greeting": "true or false - whether this is primarily just a greeting"
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
        import json
        import re
        
        # Extract JSON from the result if needed
        json_match = re.search(r'({.*})', result.raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                result_data = json.loads(json_str)
                block_type = result_data.get("block_type", "problem")  # Default to problem if parsing fails
                confidence = int(result_data.get("confidence", 7))  # Default confidence
                is_greeting = result_data.get("is_greeting", "false").lower() == "true"
                
                return block_type, confidence, is_greeting
            except json.JSONDecodeError:
                logger.error(f"Failed to parse classification result: {json_str}")
                return "problem", 5, False  # Default with low confidence
        else:
            logger.error("No JSON found in classification result")
            return "problem", 5, False  # Default with low confidence
            
    except Exception as e:
        logger.error(f"Error in classification: {str(e)}")
        return "problem", 5, False  # Default with low confidence on any error
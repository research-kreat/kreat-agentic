from crewai import Agent, Task, Crew, Process
from crewai import LLM
import logging

logger = logging.getLogger(__name__)

def classify_user_input(user_input):
    """
    Classifies the user input into one of the eight block types.
    
    Returns:
        tuple: (block_type, confidence_score)
    """
    try:
        # Initialize LLM
        llm = LLM(
            model="azure/gpt-4o-mini", 
            temperature=0.2
        )
        
        # Create classification agent
        classification_agent = Agent(
            role="Block Classifier",
            goal="Accurately classify user inputs into the correct block type",
            backstory="""You are an expert in understanding and categorizing user inputs 
            into the correct KRAFT framework block type. You analyze the semantics and 
            intent of user messages to determine which block best represents their needs.""",
            verbose=True,
            llm=llm
        )
        
        # Classification task
        classification_task = Task(
            description=f"""
            Analyze the following user input and classify it into one of the eight KRAFT framework block types:
            
            User Input: "{user_input}"
            
            The eight block types are:
            1. "idea" - Creative concepts and innovative solutions
            2. "problem" - Issues, challenges, or obstacles that need addressing
            3. "possibility" - Potential approaches or solutions to explore
            4. "moonshot" - Ambitious, potentially transformative ideas (IFR - Ideal Final Result)
            5. "needs" - Requirements, demands, or necessities
            6. "opportunity" - Favorable circumstances or chances for advancement
            7. "concept" - Structured solutions or frameworks
            8. "outcome" - Results, consequences, or end states
            
            Your output must be EXACTLY in this JSON format:
            {{
                "block_type": "one of the eight types listed above",
                "confidence": "a number between 1-10 representing your confidence",
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
                
                return block_type, confidence
            except json.JSONDecodeError:
                logger.error(f"Failed to parse classification result: {json_str}")
                return "problem", 5  # Default with low confidence
        else:
            logger.error("No JSON found in classification result")
            return "problem", 5  # Default with low confidence
            
    except Exception as e:
        logger.error(f"Error in classification: {str(e)}")
        return "problem", 5  # Default with low confidence on any error
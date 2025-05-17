from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class MoonshotBlockHandler(BaseBlockHandler):
    """
    Handler for the Moonshot block type - follows standardized flow from chat-flow.txt
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Moonshot block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "moonshot")
        
        # Create specialized agent for moonshot initialization
        moonshot_agent = Agent(
            role="Moonshot Vision Assistant",
            goal="Classify input and help users develop transformative ideas",
            backstory="""You help users think big and develop ambitious, transformative ideas through natural dialogue
            following a structured but conversational approach.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Your goal is to classify this as a moonshot vision and prepare a two-part response:
            
            PART 1: A classification message that tells the user:
            - You recognize this as a moonshot or transformative idea
            - You'll help classify it for better understanding
            - You'll decide on next steps after classification
            
            PART 2: A suggestion about generating a title 
            - Ask if they'd like to generate a title for this moonshot vision
            - Keep it conversational and brief
            - Keep it simpler and conversational
            
            FORMAT:
            {{
                "identified_as": "moonshot",
                "classification_message": "Your classification message from PART 1",
                "suggestion": "Your title question from PART 2"
            }}
            """,
            agent=moonshot_agent,
            expected_output="JSON with classification message and suggestion"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[moonshot_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Try to parse JSON from the result
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    # Ensure required fields are present
                    if "identified_as" not in result_data:
                        result_data["identified_as"] = "moonshot"
                    if "classification_message" not in result_data:
                        result_data["classification_message"] = "Great! Let's classify this moonshot vision related to your input. This will help us understand its transformative potential. Once classified, we can decide on the next steps."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to generate a title for this moonshot vision?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "moonshot",
                "classification_message": "Great! Let's classify this moonshot vision related to your input. This will help us understand its transformative potential. Once classified, we can decide on the next steps.",
                "suggestion": "Would you like to generate a title for this moonshot vision?"
            }
        except Exception as e:
            logger.error(f"Error initializing moonshot block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "moonshot",
                "classification_message": "Great! Let's classify this moonshot vision related to your input. This will help us understand its transformative potential. Once classified, we can decide on the next steps.",
                "suggestion": "Would you like to generate a title for this moonshot vision?"
            }
            
    def process_message(self, user_message, flow_status):
        """
        Process a user message for a moonshot block based on current flow status
        
        This method uses the base implementation that follows the standardized flow
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Use the base implementation that now follows the standardized flow
        return super().process_message(user_message, flow_status)
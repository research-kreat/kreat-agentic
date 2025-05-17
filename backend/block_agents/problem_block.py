from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class ProblemBlockHandler(BaseBlockHandler):
    """
    Handler for the Problem block type - follows standardized flow from chat-flow.txt
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Problem block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "problem")
        
        # Create specialized agent for problem initialization
        problem_agent = Agent(
            role="Problem Definition Assistant",
            goal="Classify input and help users clarify complex problems",
            backstory="""You help users clarify challenges through natural dialogue
            following a structured but conversational approach.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Your goal is to classify this as a problem and prepare a two-part response:
            
            PART 1: A classification message that tells the user:
            - You recognize this as a problem that needs solving
            - You'll help classify it for better understanding
            - You'll decide on next steps after classification
            
            PART 2: A suggestion about generating a title 
            - Ask if they'd like to generate a title for this problem
            - Keep it conversational and brief            
            - Keep it simpler and conversational

            
            FORMAT:
            {{
                "identified_as": "problem",
                "classification_message": "Your classification message from PART 1",
                "suggestion": "Your title question from PART 2"
            }}
            """,
            agent=problem_agent,
            expected_output="JSON with classification message and suggestion"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[problem_agent],
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
                        result_data["identified_as"] = "problem"
                    if "classification_message" not in result_data:
                        result_data["classification_message"] = "Great! Let's classify this problem related to your input. This will help us understand it better. Once classified, we can decide on the next steps."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to generate a title for this problem?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "problem",
                "classification_message": "Great! Let's classify this problem related to your input. This will help us understand it better. Once classified, we can decide on the next steps.",
                "suggestion": "Would you like to generate a title for this problem?"
            }
        except Exception as e:
            logger.error(f"Error initializing problem block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "problem",
                "classification_message": "Great! Let's classify this problem related to your input. This will help us understand it better. Once classified, we can decide on the next steps.",
                "suggestion": "Would you like to generate a title for this problem?"
            }
            
    def process_message(self, user_message, flow_status):
        """
        Process a user message for a problem block based on current flow status
        
        This method uses the base implementation that follows the standardized flow
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Use the base implementation that now follows the standardized flow
        return super().process_message(user_message, flow_status)
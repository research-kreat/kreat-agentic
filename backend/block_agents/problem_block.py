from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class ProblemBlockHandler(BaseBlockHandler):
    """
    Handler for the Problem block type with concise conversational flow
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
            following a structured approach without over-explaining.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Prepare a two-part response:
            
            PART 1: A brief classification message that acknowledges this as a problem. Keep it to 1-2 sentences max.
            
            PART 2: A simple question asking if they'd like to generate a title.
            
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
                        result_data["classification_message"] = "Great! Let's classify this problem. This will help us understand it better."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to generate a title for this problem?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "problem",
                "classification_message": "Great! Let's classify this problem. This will help us understand it better.",
                "suggestion": "Would you like to generate a title for this problem?"
            }
        except Exception as e:
            logger.error(f"Error initializing problem block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "problem",
                "classification_message": "Great! Let's classify this problem. This will help us understand it better.",
                "suggestion": "Would you like to generate a title for this problem?"
            }
            
    def process_message(self, user_message, flow_status):
        """
        Process a user message for a problem block based on current flow status
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Use the base implementation that follows the standardized flow
        return super().process_message(user_message, flow_status)
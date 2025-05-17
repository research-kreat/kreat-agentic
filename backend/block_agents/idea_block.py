from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Handler for the Idea block type - follows standardized flow from chat-flow.txt
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Idea block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "idea")
        
        # Create specialized agent for idea initialization
        idea_agent = Agent(
            role="Idea Development Assistant",
            goal="Classify input and help users develop innovative ideas",
            backstory="""You help users refine their ideas through natural dialogue
            following a structured but conversational approach.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Your goal is to classify this as an idea and prepare a two-part response:
            
            PART 1: A classification message that tells the user:
            - You recognize this as an idea
            - You'll help classify it for better understanding
            - You'll decide on next steps after classification
            
            PART 2: A suggestion about generating a title 
            - Ask if they'd like to generate a title for their idea
            - Keep it simpler and conversational
            
            FORMAT:
            {{
                "identified_as": "idea",
                "classification_message": "Your classification message from PART 1",
                "suggestion": "Your title question from PART 2"
            }}
            """,
            agent=idea_agent,
            expected_output="JSON with classification message and suggestion"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[idea_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Try to parse JSON from the result
            import json
            import re
            
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    # Ensure required fields are present
                    if "identified_as" not in result_data:
                        result_data["identified_as"] = "idea"
                    if "classification_message" not in result_data:
                        result_data["classification_message"] = "Great! I've identified this as an idea. Let's explore it further and decide on next steps."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to generate a title for this idea?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "idea",
                "classification_message": "Great! I've identified this as an idea. Let's explore it further and decide on next steps.",
                "suggestion": "Would you like to generate a title for this idea?"
            }
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "classification_message": "Great! I've identified this as an idea. Let's explore it further and decide on next steps.",
                "suggestion": "Would you like to generate a title for this idea?"
            }
            
    def process_message(self, user_message, flow_status):
        """
        Process a user message for an idea block based on current flow status
        
        This method overrides the base implementation to use the standardized chat flow
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Use the base implementation that now follows the standardized flow
        return super().process_message(user_message, flow_status)
from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Handler for the Idea block type with concise conversational flow
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
            following a structured but conversational approach without over-explaining.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Prepare a two-part response:
            
            PART 1: A brief classification message that acknowledges this as an idea. Just 1-2 sentences.
            
            PART 2: A friendly message that shows excitement about the idea and invites the user to proceed with title generation. 
            Make it conversational and encouraging.
            
            FORMAT:
            {{
                "identified_as": "idea",
                "classification_message": "Your classification message from PART 1",
                "suggestion": "Your follow-up message from PART 2"
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
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    # Ensure required fields are present
                    if "identified_as" not in result_data:
                        result_data["identified_as"] = "idea"
                    if "classification_message" not in result_data:
                        result_data["classification_message"] = "Great! I've identified this as an idea. Let's explore it further."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "It's a great idea! Would you like to proceed with generating a title for it?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "idea",
                "classification_message": "Great! I've identified this as an idea. Let's explore it further.",
                "suggestion": "It's a great idea! Would you like to proceed with generating a title for it?"
            }
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "classification_message": "Great! I've identified this as an idea. Let's explore it further.",
                "suggestion": "It's a great idea! Would you like to proceed with generating a title for it?"
            }
            
    def process_message(self, user_message, flow_status):
        """
        Process a user message for an idea block based on current flow status
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Use the base implementation that follows the standardized flow
        return super().process_message(user_message, flow_status)
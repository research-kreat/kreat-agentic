from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Enhanced handler for the Idea block type with improved safety measures
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
        
        # Create specialized agent with safety measures
        idea_agent = Agent(
            role="Idea Development Assistant",
            goal="Classify input and help users develop innovative ideas",
            backstory="""You help users refine their ideas through natural dialogue
            following a structured but conversational approach without over-explaining.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis with safety guidelines
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            IMPORTANT SAFETY GUIDELINES:
            - Focus only on the technical and consumer aspects of the idea
            - Avoid any potentially controversial content
            - Do not include any content related to politics, weapons, or sensitive topics
            - Keep all content neutral and product-focused
            
            Prepare a two-part response in pure JSON format:
            
            PART 1: A brief classification message that acknowledges this as an idea. Just 1-2 sentences.
            
            PART 2: A friendly message that invites the user to generate a title. 
            Make it conversational and encouraging.
            
            FORMAT:
            {{
                "identified_as": "idea",
                "classification_message": "Your classification message from PART 1",
                "suggestion": "Would you like to generate a title for this idea?"
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
                        result_data["classification_message"] = "I've identified this as an innovative idea. Let's develop it further."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to generate a title for this idea?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "idea",
                "classification_message": "I've identified this as an innovative idea. Let's develop it further.",
                "suggestion": "Would you like to generate a title for this idea?"
            }
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "classification_message": "I've identified this as an innovative idea. Let's develop it further.",
                "suggestion": "Would you like to generate a title for this idea?"
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
        # Get conversation history
        history = self._get_conversation_history(limit=20)
        
        # Check if the message is a greeting
        if self.is_greeting(user_message):
            return self.handle_greeting(user_message, "idea")
        
        # Determine if user is confirming to proceed
        is_confirmation = self._is_user_confirmation(user_message)
        
        # Get previously generated content
        previous_content = self._get_previous_content(history)
        
        # Find the current step based on flow status
        current_step = self._get_current_step(flow_status, previous_content)
        
        # Find the next step to suggest
        current_status = flow_status.copy()
        if current_step:
            current_status[current_step] = True
        next_step = self._get_next_step(current_status, previous_content)
        
        if not current_step:
            # If all steps are completed, check for required steps
            missing_required = self._check_missing_required_steps(previous_content)
            if missing_required:
                current_step = missing_required[0]
                return self._generate_contextual_response(user_message, current_step, flow_status, history)
            else:
                # All steps completed
                title_context = f" for '{previous_content.get('title')}'" if 'title' in previous_content else ""
                return {"suggestion": f"We've covered all the main aspects{title_context}. What would you like to explore next?"}
            
        if is_confirmation:
            # Generate content for current step
            result = self._generate_step_content_and_suggestion(current_step, user_message, flow_status, history, previous_content)
            
            # Apply word limits if needed
            if current_step in self.word_limits and current_step in result:
                result[current_step] = self._enforce_word_limit(result[current_step], self.word_limits[current_step])
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            result["updated_flow_status"] = updated_flow_status
            
            # Ensure suggestion is for the correct next step
            if "suggestion" in result and next_step:
                next_step_desc = self.step_descriptions.get(next_step, next_step)
                title_ref = f" for '{previous_content.get('title')}'" if 'title' in previous_content else ""
                result["suggestion"] = f"Would you like to generate {next_step_desc}{title_ref}?"
            
            return result
        else:
            # Handle non-confirmation input
            response = self._generate_contextual_response(user_message, current_step, flow_status, history)
            
            # Ensure correct suggestion
            current_step_desc = self.step_descriptions.get(current_step, current_step)
            title_ref = f" for '{previous_content.get('title')}'" if 'title' in previous_content else ""
            response["suggestion"] = f"Would you like to generate {current_step_desc}{title_ref}?"
            
            return response
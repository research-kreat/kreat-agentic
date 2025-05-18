from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Enhanced handler for the Idea block type with improved conversation flow
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
            backstory="You help users refine their ideas through natural dialogue.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Prepare a two-part response in JSON format:
            
            PART 1: A brief classification message that acknowledges this as an idea. Keep it conversational and brief.
            
            PART 2: A friendly message that shows interest in the idea and invites the user to generate a title. 
            Make it natural and encouraging.
            
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
                        result_data["classification_message"] = "I've identified this as an innovative idea. Let's explore it further."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to create a title for this idea?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "idea",
                "classification_message": "I've identified this as an innovative idea. Let's explore it further.",
                "suggestion": "Would you like to create a title for this idea?"
            }
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "classification_message": "I've identified this as an innovative idea. Let's explore it further.",
                "suggestion": "Would you like to create a title for this idea?"
            }
    
    def process_message(self, user_message, flow_status):
        """
        Process a user message for an idea block based on current flow status
        
        This implementation adds some idea-specific handling before falling back
        to the base implementation for standard flow steps
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # First, check if this is a greeting
        if self.is_greeting(user_message):
            return self.handle_greeting(user_message, "idea")
            
        # Get conversation history and previous content
        history = self._get_conversation_history()
        previous_content = self._get_previous_content(history)
        
        # Get the current step
        current_step = self._get_current_step(flow_status, previous_content)
        
        # If we don't have a current step, all are complete
        if not current_step:
            # Provide a summary and suggestions for next actions
            title = previous_content.get('title', 'your idea')
            return {
                "suggestion": f"We've explored all the main aspects of \"{title}\". Would you like to review specific elements or consider how to implement this idea?"
            }
            
        # For idea blocks, we can add custom handling for specific steps
        if current_step == "title" and self._is_user_confirmation(user_message):
            # If user confirms for title generation, use our custom handler
            return self._generate_creative_title(user_message, previous_content)
        elif current_step == "abstract" and 'title' in previous_content and self._is_user_confirmation(user_message):
            # For abstract generation with a title, use custom handler
            return self._generate_abstract_from_title(user_message, previous_content)
            
        # For all other steps, use the standard process from base class
        return super().process_message(user_message, flow_status)
        
    def _generate_creative_title(self, user_message, previous_content):
        """Generate a creative title for the idea
        
        Args:
            user_message: User's message
            previous_content: Previously generated content
            
        Returns:
            dict: Response with title and next suggestion
        """
        try:
            # Get block data
            block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
            initial_input = block_data.get("initial_input", "")
            
            # Create agent for title generation
            title_agent = Agent(
                role="Creative Title Designer",
                goal="Generate compelling, memorable titles for innovations",
                backstory="You craft concise titles that capture the essence of ideas.",
                verbose=True,
                llm=self.llm
            )
            
            # Create task
            title_task = Task(
                description=f"""
                The user wants a title for this idea:
                
                Original concept: "{initial_input}"
                
                Generate a compelling, memorable title that:
                - Captures the essence of the concept
                - Is clear and specific
                - Is engaging and memorable
                
                Format your response as JSON:
                {{
                    "title": "The generated title",
                    "suggestion": "Would you like to create an abstract that explains this idea?"
                }}
                """,
                agent=title_agent,
                expected_output="JSON with title and suggestion"
            )
            
            # Execute task
            crew = Crew(
                agents=[title_agent],
                tasks=[title_task],
                process=Process.sequential,
                verbose=True
            )
            
            result = crew.kickoff()
            
            # Parse result
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    
                    # Ensure required fields and update flow status
                    if "title" not in result_data or not result_data["title"]:
                        result_data["title"] = f"Innovative Solution: {initial_input}"
                        
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to create an abstract that explains this idea?"
                    
                    # Update flow status
                    updated_flow_status = {step: False for step in self.flow_steps}
                    updated_flow_status["title"] = True
                    result_data["updated_flow_status"] = updated_flow_status
                    result_data["current_step_completed"] = "title"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse title generation result: {result.raw}")
            
            # Fallback
            return {
                "title": f"Innovative Solution: {initial_input[:50]}{'...' if len(initial_input) > 50 else ''}",
                "suggestion": "Would you like to create an abstract that explains this idea?",
                "updated_flow_status": {**{step: False for step in self.flow_steps}, **{"title": True}},
                "current_step_completed": "title"
            }
            
        except Exception as e:
            logger.error(f"Error generating title: {str(e)}")
            
            # Fallback
            return {
                "title": f"Innovative Solution: {initial_input[:50]}{'...' if len(initial_input) > 50 else ''}",
                "suggestion": "Would you like to create an abstract that explains this idea?",
                "updated_flow_status": {**{step: False for step in self.flow_steps}, **{"title": True}},
                "current_step_completed": "title"
            }
    
    def _generate_abstract_from_title(self, user_message, previous_content):
        """Generate an abstract based on the title
        
        Args:
            user_message: User's message
            previous_content: Previously generated content including title
            
        Returns:
            dict: Response with abstract and next suggestion
        """
        try:
            # Get block data
            block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
            initial_input = block_data.get("initial_input", "")
            title = previous_content.get("title", f"Innovative Solution: {initial_input}")
            
            # Create agent for abstract generation
            abstract_agent = Agent(
                role="Concept Developer",
                goal="Create clear, compelling abstracts for innovative ideas",
                backstory="You help innovators articulate their ideas clearly and effectively.",
                verbose=True,
                llm=self.llm
            )
            
            # Create task
            abstract_task = Task(
                description=f"""
                Create an abstract for this idea:
                
                Original concept: "{initial_input}"
                Title: "{title}"
                
                Generate a concise abstract that:
                - Explains what the idea is
                - Describes why it matters and its potential impact
                - Uses clear, professional language
                
                Format your response as JSON:
                {{
                    "abstract": "The generated abstract",
                    "suggestion": "Would you like to identify the key stakeholders involved in this idea?"
                }}
                """,
                agent=abstract_agent,
                expected_output="JSON with abstract and suggestion"
            )
            
            # Execute task
            crew = Crew(
                agents=[abstract_agent],
                tasks=[abstract_task],
                process=Process.sequential,
                verbose=True
            )
            
            result = crew.kickoff()
            
            # Parse result
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    
                    # Ensure required fields
                    if "abstract" not in result_data or not result_data["abstract"]:
                        result_data["abstract"] = f"This is an innovative concept based on {title}. It aims to address key challenges and create meaningful impact in its domain."
                        
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Would you like to identify the key stakeholders involved in this idea?"
                    
                    # Update flow status
                    updated_flow_status = {step: False for step in self.flow_steps}
                    updated_flow_status["title"] = True
                    updated_flow_status["abstract"] = True
                    result_data["updated_flow_status"] = updated_flow_status
                    result_data["current_step_completed"] = "abstract"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse abstract generation result: {result.raw}")
            
            # Fallback
            return {
                "abstract": f"This is an innovative concept titled '{title}'. It addresses key challenges and creates impact through its novel approach.",
                "suggestion": "Would you like to identify the key stakeholders involved in this idea?",
                "updated_flow_status": {**{step: False for step in self.flow_steps}, **{"title": True, "abstract": True}},
                "current_step_completed": "abstract"
            }
            
        except Exception as e:
            logger.error(f"Error generating abstract: {str(e)}")
            
            # Fallback
            return {
                "abstract": f"This is an innovative concept titled '{title}'. It addresses key challenges and creates impact through its novel approach.",
                "suggestion": "Would you like to identify the key stakeholders involved in this idea?",
                "updated_flow_status": {**{step: False for step in self.flow_steps}, **{"title": True, "abstract": True}},
                "current_step_completed": "abstract"
            }
from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process
import json
import re

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Enhanced handler for the Idea block type with improved dynamic suggestions  
    and better use of conversation history
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
        
        # Create task for initial analysis with more conversational guidance
        analysis_task = Task(
            description=f"""
            The user has shared this initial input:
            
            "{user_input}"
            
            Analyze this input and prepare a two-part response:
            
            PART 1: A brief, conversational message that acknowledges this as an idea worth exploring.
            Make it sound natural and enthusiastic without being overly formal.
            Avoid phrases like "I've identified this as..." or "Let me help you with..."
            
            PART 2: A friendly message that shows interest in the idea and invites the user 
            to generate a title. Sound like a real person having a conversation.
            
            FORMAT:
            {{
                "identified_as": "idea",
                "classification_message": "Your message from PART 1",
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
                        result_data["classification_message"] = "That's a fascinating idea. I can see a lot of potential in exploring it further."
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Want to come up with a catchy title for this idea?"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            return {
                "identified_as": "idea",
                "classification_message": "That's a fascinating idea. I can see a lot of potential in exploring it further.",
                "suggestion": "Want to come up with a catchy title for this idea?"
            }
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "classification_message": "That's a fascinating idea. I can see a lot of potential in exploring it further.",
                "suggestion": "Want to come up with a catchy title for this idea?"
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
            # Generate a dynamic completion message using title if available
            title = previous_content.get('title', 'your idea')
            
            try:
                # Create agent for generating a dynamic completion message
                agent = Agent(
                    role="Idea Development Coach",
                    goal="Provide insightful guidance on idea development",
                    backstory="You help innovators refine and implement ideas through thoughtful conversation.",
                    verbose=True,
                    llm=self.llm
                )
                
                # Get recent messages for context
                recent_messages = ""
                if history and len(history) >= 2:
                    for msg in history[-2:]:
                        if msg.get("role") == "user":
                            recent_messages += f"User said: \"{msg.get('message', '')[:100]}\"\n"
                
                # Task for dynamic completion
                task = Task(
                    description=f"""
                    The user has completed exploring all aspects of their idea titled "{title}".
                    
                    Abstract: {previous_content.get('abstract', 'Not available')}
                    Recent messages: {recent_messages}
                    
                    Create a natural, conversational response that:
                    1. Shows genuine interest in their idea's development
                    2. Suggests 1-2 specific next steps they might want to consider
                    3. Sounds like a real person (not an AI assistant)
                    
                    Your response should be brief (2-3 sentences) and avoid phrases like 
                    "I can help you" or "Would you like me to".
                    """,
                    agent=agent,
                    expected_output="A conversational completion message"
                )
                
                crew = Crew(
                    agents=[agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=True
                )
                
                result = crew.kickoff()
                return {"suggestion": result.raw.strip()}
                
            except Exception as e:
                logger.error(f"Error generating completion message: {str(e)}")
                return {"suggestion": f"We've explored all the key aspects of \"{title}\". What specific part would you like to develop further?"}
            
        # For title generation with confirmation, use enhanced method
        if current_step == "title" and self._is_user_confirmation(user_message):
            return self._generate_creative_title(user_message, previous_content, flow_status, history)
            
        # For abstract generation with a title and confirmation, use enhanced method
        elif current_step == "abstract" and 'title' in previous_content and self._is_user_confirmation(user_message):
            return self._generate_abstract_from_title(user_message, previous_content, flow_status, history)
            
        # For all other steps, use the standard process from base class
        return super().process_message(user_message, flow_status)
        
    def _generate_creative_title(self, user_message, previous_content, flow_status, history=None):
        """Generate a creative title for the idea with conversation history context
        
        Args:
            user_message: User's message
            previous_content: Previously generated content
            flow_status: Current flow status
            history: Conversation history
            
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
            
            # Get recent conversation for context
            recent_conversation = ""
            if history:
                # Get the last 3 messages
                last_messages = history[-min(3, len(history)):]
                for msg in last_messages:
                    role = msg.get("role", "")
                    content = msg.get("message", "")[:100]
                    if content:
                        recent_conversation += f"{role.capitalize()}: {content}...\n"
            
            # Create task with conversation history
            title_task = Task(
                description=f"""
                The user wants a title for this idea:
                
                Original idea: "{initial_input}"
                
                Recent conversation:
                {recent_conversation}
                
                Generate a compelling, memorable title that:
                - Captures the essence of the concept
                - Is clear and specific (not generic)
                - Uses engaging, vibrant language
                - Is memorable and distinctive
                
                Then create a brief, conversational suggestion about creating an abstract.
                Make it sound natural, like something a creative collaborator would say.
                
                Format your response as JSON:
                {{
                    "title": "The generated title",
                    "suggestion": "Your natural suggestion about creating an abstract"
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
                        result_data["title"] = f"Innovative Solution: {initial_input[:40]}..."
                        
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Want to craft a short abstract that explains what this idea is all about?"
                    
                    # Update flow status
                    updated_flow_status = flow_status.copy()
                    updated_flow_status["title"] = True
                    result_data["updated_flow_status"] = updated_flow_status
                    result_data["current_step_completed"] = "title"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse title generation result: {result.raw}")
            
            # Fallback
            return {
                "title": f"Innovative Solution: {initial_input[:40]}...",
                "suggestion": "Want to craft a short abstract that explains what this idea is all about?",
                "updated_flow_status": {**flow_status, **{"title": True}},
                "current_step_completed": "title"
            }
            
        except Exception as e:
            logger.error(f"Error generating title: {str(e)}")
            
            # Fallback
            return {
                "title": f"Innovative Solution: {initial_input[:40]}...",
                "suggestion": "Want to craft a short abstract that explains what this idea is all about?",
                "updated_flow_status": {**flow_status, **{"title": True}},
                "current_step_completed": "title"
            }
    
    def _generate_abstract_from_title(self, user_message, previous_content, flow_status, history=None):
        """Generate an abstract based on the title with conversation history context
        
        Args:
            user_message: User's message
            previous_content: Previously generated content including title
            flow_status: Current flow status
            history: Conversation history
            
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
            
            # Get recent conversation for context
            recent_conversation = ""
            if history:
                # Get the last 3 messages
                last_messages = history[-min(3, len(history)):]
                for msg in last_messages:
                    role = msg.get("role", "")
                    content = msg.get("message", "")[:100]
                    if content:
                        recent_conversation += f"{role.capitalize()}: {content}...\n"
            
            # Create task with conversation history
            abstract_task = Task(
                description=f"""
                Create an abstract for this idea:
                
                Original idea: "{initial_input}"
                Title: "{title}"
                
                Recent conversation:
                {recent_conversation}
                
                Generate a concise abstract that:
                - Clearly explains what the idea is
                - Highlights why it matters and its potential impact
                - Mentions key benefits or applications
                - Uses professional but accessible language
                
                Then create a natural, conversational suggestion about identifying stakeholders.
                Make it sound like something a colleague would say, not an AI assistant.
                
                Format your response as JSON:
                {{
                    "abstract": "The generated abstract",
                    "suggestion": "Your natural suggestion about identifying stakeholders"
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
                        result_data["abstract"] = f"This innovation titled '{title}' addresses key challenges and offers a novel approach to solving problems. It has the potential to create meaningful impact through improved efficiency and enhanced user experience."
                        
                    if "suggestion" not in result_data:
                        result_data["suggestion"] = "Who are the main people or groups that would be involved with or affected by this idea?"
                    
                    # Update flow status
                    updated_flow_status = flow_status.copy()
                    updated_flow_status["title"] = True
                    updated_flow_status["abstract"] = True
                    result_data["updated_flow_status"] = updated_flow_status
                    result_data["current_step_completed"] = "abstract"
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse abstract generation result: {result.raw}")
            
            # Fallback
            return {
                "abstract": f"This innovation titled '{title}' addresses key challenges and offers a novel approach to solving problems. It has the potential to create meaningful impact through improved efficiency and enhanced user experience.",
                "suggestion": "Who are the main people or groups that would be involved with or affected by this idea?",
                "updated_flow_status": {**flow_status, **{"title": True, "abstract": True}},
                "current_step_completed": "abstract"
            }
            
        except Exception as e:
            logger.error(f"Error generating abstract: {str(e)}")
            
            # Fallback
            return {
                "abstract": f"This innovation titled '{title}' addresses key challenges and offers a novel approach to solving problems. It has the potential to create meaningful impact through improved efficiency and enhanced user experience.",
                "suggestion": "Who are the main people or groups that would be involved with or affected by this idea?",
                "updated_flow_status": {**flow_status, **{"title": True, "abstract": True}},
                "current_step_completed": "abstract"
            }
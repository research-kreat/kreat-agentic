from abc import ABC, abstractmethod
import logging
from crewai import Agent, Task, Crew, Process
from crewai import LLM
import json
import re

logger = logging.getLogger(__name__)

class BaseBlockHandler(ABC):
    """
    Base class for all block handlers with improved error handling and flow control
    """
    
    def __init__(self, db, block_id, user_id):
        """Initialize the block handler
        
        Args:
            db: MongoDB database instance
            block_id: ID of the block
            user_id: ID of the user
        """
        self.db = db
        self.block_id = block_id
        self.user_id = user_id
        self.flow_collection = db.flow_status
        self.history_collection = db.conversation_history
        
        # Initialize LLM with moderate temperature for creativity
        self.llm = LLM(
            model="azure/gpt-4o-mini",
            temperature=0.7
        )
        
        # Standard flow steps in the correct order
        self.flow_steps = [
            "title",
            "abstract",
            "stakeholders",
            "tags",
            "assumptions",
            "constraints",
            "risks",
            "areas",
            "impact",
            "connections",
            "classifications",
            "think_models"
        ]
        
        # Mark title and abstract as required and priority steps
        self.required_steps = ["title", "abstract"]
        self.priority_steps = ["title", "abstract"]
        
        # Human-readable step descriptions for prompts
        self.step_descriptions = {
            "title": "a compelling title",
            "abstract": "a clear summary",
            "stakeholders": "key people or groups involved",
            "tags": "relevant keywords",
            "assumptions": "underlying assumptions",
            "constraints": "limitations or restrictions",
            "risks": "potential challenges",
            "areas": "related fields or domains",
            "impact": "key benefits and outcomes",
            "connections": "related concepts",
            "classifications": "categorization schemes",
            "think_models": "thinking frameworks"
        }
    
    def is_greeting(self, user_input):
        """Check if the user input is a greeting"""
        greeting_phrases = [
            "hi", "hello", "hey", "greetings", "good morning", "good afternoon", 
            "good evening", "howdy", "what's up", "how are you", "nice to meet you",
            "how's it going", "sup", "yo", "hiya", "hi there", "hello there",
            "hey there", "welcome", "good day", "how do you do", "how's everything"
        ]

        clean_input = user_input.lower().strip()
        
        # Check if input starts with greeting phrase or is a greeting
        for phrase in greeting_phrases:
            if clean_input.startswith(phrase) or clean_input == phrase:
                return True
                
        return False
    
    def handle_greeting(self, user_input, block_type):
        """Handle greeting with natural, concise responses"""
        history = self._get_conversation_history()
        previous_content = self._get_previous_content(history)
        block_context = self._get_block_context(previous_content, block_type)
        
        # Block-specific contexts for better conversation
        block_contexts = {
            "idea": "innovative ideas",
            "problem": "problems worth solving",
            "possibility": "potential solutions",
            "moonshot": "ambitious visions",
            "needs": "requirements to address",
            "opportunity": "promising opportunities",
            "concept": "structured solutions",
            "outcome": "results to achieve",
            "general": "creative thinking"
        }
        
        context = block_contexts.get(block_type, "creative thinking")
        
        try:
            # Create agent for generating natural greeting
            agent = Agent(
                role="Conversation Guide",
                goal="Engage users in a friendly conversation about innovation",
                backstory="You help people develop creative innovations with concise, natural responses.",
                verbose=True,
                llm=self.llm
            )
            
            # Task for generating greeting response
            task = Task(
                description=f"""
                The user has greeted you with: "{user_input}"
                
                {block_context}
                
                You're having a conversation about {context}.
                
                Respond with a brief, friendly greeting that:
                1. Acknowledges their greeting
                2. References the current title/topic if available
                3. Asks an open-ended question about {context} they're thinking about
                
                Keep your response very concise (1-2 sentences).
                Don't use bullet points or numbered lists.
                Just ask naturally, avoiding phrases like "I can help you with..." or "Would you like to..."
                """,
                agent=agent,
                expected_output="A brief, friendly greeting"
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            result = crew.kickoff()
            return {
                "identified_as": "greeting",
                "greeting_response": result.raw.strip()
            }
        except Exception as e:
            logger.error(f"Error generating greeting response: {str(e)}")
            
            # Create contextual fallback greeting
            title_context = f" about '{previous_content.get('title')}'" if 'title' in previous_content else ""
            default_greeting = f"Hey there! What {block_type}{title_context} are you thinking about today?"
            
            return {
                "identified_as": "greeting",
                "greeting_response": default_greeting
            }
    
    def _get_block_context(self, previous_content, block_type):
        """Generate context text based on previously generated content"""
        if not previous_content:
            return ""
            
        context_parts = []
        
        # Add title if available
        if 'title' in previous_content:
            context_parts.append(f"Title: {previous_content['title']}")
        
        # Add abstract if available
        if 'abstract' in previous_content:
            context_parts.append(f"Abstract: {previous_content['abstract']}")
        
        # Only return context if we have content
        if context_parts:
            type_label = block_type.capitalize()
            return f"Current {type_label} Context:\n" + "\n".join(context_parts)
        
        return ""
    
    @abstractmethod
    def initialize_block(self, user_input):
        """Initialize a new block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with suggestion for next step
        """
        pass
    
    def process_message(self, user_message, flow_status):
        """Process user message based on current flow status"""
        # Check if the message is a greeting
        if self.is_greeting(user_message):
            block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
            block_type = block_data.get("block_type", "general")
            return self.handle_greeting(user_message, block_type)
        
        # Get conversation history and previous content
        history = self._get_conversation_history()
        previous_content = self._get_previous_content(history)
        
        # Determine if user is confirming to proceed with current step
        is_confirmation = self._is_user_confirmation(user_message)
        
        # Find the current step based on flow status
        current_step = self._get_current_step(flow_status, previous_content)
        
        if not current_step:
            # All steps completed, provide contextual completion message
            title_context = f" for '{previous_content.get('title')}'" if 'title' in previous_content else ""
            return {"suggestion": f"We've covered all the main aspects{title_context}. What would you like to explore next?"}
            
        if is_confirmation:
            # User confirms to proceed - generate content for current step
            result = self._generate_step_content_and_suggestion(current_step, user_message, flow_status, history, previous_content)
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Add updated flow status to the response
            result["updated_flow_status"] = updated_flow_status
            result["current_step_completed"] = current_step
            
            return result
        else:
            # User provided content or other input - respond contextually
            return self._generate_contextual_response(user_message, current_step, flow_status, history)
    
    def _is_user_confirmation(self, message):
        """Check if the user message is a confirmation to proceed"""
        message = message.lower().strip()
        
        # Common confirmation phrases
        confirmation_phrases = [
            "ok", "okay", "yes", "yeah", "yep", "sure", "proceed", 
            "let's do it", "go ahead", "continue", "generate", "please do",
            "sounds good", "good", "great", "perfect", "do it",
            "i'm ready", "ready", "let's go", "go for it", "next",
            "that's great", "thats great", "lets go", "let's continue"
        ]
        
        # Check for exact matches or if message starts with confirmation
        if message in confirmation_phrases:
            return True
            
        for phrase in confirmation_phrases:
            if message.startswith(phrase) or f" {phrase} " in f" {message} ":
                return True
                
        return False
    
    def _generate_step_content_and_suggestion(self, current_step, user_message, flow_status, history, previous_content):
        """Generate content for the current step and suggestion for the next step"""
        # Get the initial input and block type
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        block_type = block_data.get("block_type", "general")
        
        # Find the next step
        next_status = flow_status.copy()
        next_status[current_step] = True
        next_step = self._get_next_step(next_status, previous_content)
        next_step_desc = self.step_descriptions.get(next_step, next_step) if next_step else "the next aspect"
        
        # Prepare context for the prompt
        context = self._prepare_step_context(current_step, initial_input, previous_content, block_type)
        
        try:
            # Create agent for content generation
            agent = Agent(
                role="Creative Thinking Partner",
                goal=f"Generate {self.step_descriptions.get(current_step, current_step)} for the user's {block_type}",
                backstory="You help people develop innovations through structured thinking with natural responses.",
                verbose=True,
                llm=self.llm
            )
            
            # Create task for content generation
            task = Task(
                description=f"""
                {context}
                
                You need to generate:
                1. {self.step_descriptions.get(current_step, current_step)} for this {block_type}
                
                Guidelines for "{current_step}":
                {self._get_step_guidelines(current_step)}
                
                2. A simple question asking if the user wants to continue to the next step: {next_step}.
                
                Format your response as JSON:
                {{
                    "{current_step}": // Content for the current step
                    "suggestion": // A simple question about continuing to the next step: {next_step}.
                }}
                
                Keep your response:
                - Clear and focused on the topic
                - Following the specified format
                - Including only these two elements without extra explanations
                """,
                agent=agent,
                expected_output=f"JSON with {current_step} content and next step suggestion"
            )
            
            # Execute task
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            result = crew.kickoff()
            
            # Parse result as JSON
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    
                    # Format the current step content
                    current_step_content = result_data.get(current_step)
                    if current_step_content:
                        result_data[current_step] = self._parse_step_result(current_step, json.dumps(current_step_content) if isinstance(current_step_content, (list, dict)) else current_step_content)
                    
                    # Ensure suggestion is present
                    if "suggestion" not in result_data or not result_data["suggestion"]:
                        title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
                        
                        if next_step:
                            result_data["suggestion"] = f"Would you like to generate {next_step_desc}{title_context}?"
                        else:
                            result_data["suggestion"] = f"Great! We've completed all the steps{title_context}. What would you like to explore next?"
                    
                    return result_data
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback for parsing failures
            title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
            
            return {
                current_step: f"Let's try a different approach for generating {self.step_descriptions.get(current_step, current_step)}{title_context}.",
                "suggestion": f"Would you like to try generating {next_step_desc}{title_context}?" if next_step else f"What would you like to explore next{title_context}?"
            }
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            
            # Fallback response
            title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
            
            return {
                current_step: f"Let's try a different approach for generating {self.step_descriptions.get(current_step, current_step)}{title_context}.",
                "suggestion": f"Would you like to try generating {next_step_desc}{title_context}?" if next_step else f"What would you like to explore next{title_context}?"
            }
    
    def _parse_step_result(self, step, raw_result):
        """Parse the result based on the step type"""
        # For structured data steps, try to extract JSON or format as list
        structured_steps = ["stakeholders", "tags", "assumptions", "constraints", "risks", 
                           "areas", "impact", "connections", "classifications", "think_models"]
        
        if step in structured_steps:
            # Try to find JSON in the result
            json_match = re.search(r'({.*}|\[.*\])', raw_result, re.DOTALL)
            
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
                    
            # If JSON parsing fails, return formatted list
            return self._format_bullet_list(raw_result)
        else:
            # For title and abstract, return as plain text
            return raw_result.strip()
    
    def _format_bullet_list(self, text):
        """Format text as a bullet list if it contains bullet points"""
        lines = text.strip().split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Remove the bullet character and space
                cleaned_line = line[1:].strip()
                formatted_lines.append(cleaned_line)
            elif line and not line.startswith('#') and not line.endswith(':'):
                # Non-empty lines that aren't headers or list intros
                formatted_lines.append(line)
        
        return formatted_lines if formatted_lines else text.strip()
    
    def _generate_contextual_response(self, user_message, current_step, flow_status, history):
        """Generate a contextual response for user input that's not a direct confirmation"""
        # Get data for context
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        block_type = block_data.get("block_type", "general")
        previous_content = self._get_previous_content(history)
        
        try:
            # Create agent for contextual responses
            agent = Agent(
                role="Conversation Guide",
                goal="Guide users through the creative thinking process",
                backstory="You help users develop innovations with concise, natural responses.",
                verbose=True,
                llm=self.llm
            )
            
            # Create task for generating response
            task = Task(
                description=f"""
                Block Type: {block_type}
                Current Step: {current_step} ({self.step_descriptions.get(current_step, current_step)})
                Previous Content: {json.dumps(previous_content, default=str)[:500]}
                
                User's latest message: "{user_message}"
                
                Create a brief, natural response in JSON format that suggests generating content for the current step.
                
                Format your response as:
                {{
                    "suggestion": "Your 1-2 sentence response that asks if they'd like to proceed with the current step",
                    "current_step": "{current_step}"
                }}
                
                Your response should be:
                - Conversational and brief (1-2 sentences)
                - Ask if they'd like to proceed with generating {self.step_descriptions.get(current_step, current_step)}
                - Use no bullet points, numbered lists, or explanations
                """,
                agent=agent,
                expected_output="JSON with suggestion"
            )
            
            # Execute the task
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            result = crew.kickoff()
            
            # Try to parse JSON from the result
            json_match = re.search(r'({.*})', result.raw, re.DOTALL)
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    # Ensure suggestion is present
                    if "suggestion" not in result_data:
                        title_ref = f" for '{previous_content['title']}'" if 'title' in previous_content else ""
                        result_data["suggestion"] = f"Would you like to generate {self.step_descriptions.get(current_step, current_step)}{title_ref}?"
                    
                    # Add the current step for UI display
                    result_data["current_step"] = current_step
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            title_ref = f" for '{previous_content['title']}'" if 'title' in previous_content else ""
            return {
                "suggestion": f"Would you like to generate {self.step_descriptions.get(current_step, current_step)}{title_ref}?",
                "current_step": current_step
            }
            
        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            title_ref = f" for '{previous_content['title']}'" if 'title' in previous_content else ""
            return {
                "suggestion": f"Would you like to generate {self.step_descriptions.get(current_step, current_step)}{title_ref}?",
                "current_step": current_step
            }
    
    def _get_current_step(self, flow_status, previous_content):
        """Get the current step based on flow status and previous content"""
        # First check for required steps
        for step in self.required_steps:
            if not flow_status.get(step, False) and (step not in previous_content or not previous_content[step]):
                return step
                
        # Then follow the standard order
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
        return None
    
    def _get_next_step(self, flow_status, previous_content):
        """Get the next step after the current one"""
        # First, collect steps that need to be completed
        steps_to_complete = []
        
        # Required steps that are missing have top priority
        for step in self.required_steps:
            if not flow_status.get(step, False) and (step not in previous_content or not previous_content[step]):
                steps_to_complete.append(step)
        
        # Then add all other steps from the flow that haven't been completed
        for step in self.flow_steps:
            if not flow_status.get(step, False) and step not in steps_to_complete:
                steps_to_complete.append(step)
        
        # Find the next step (second one that needs to be completed)
        if len(steps_to_complete) > 1:
            return steps_to_complete[1]
        
        return None
    
    def _get_conversation_history(self, limit=20):
        """Get the conversation history for context"""
        history = list(self.history_collection.find(
            {"block_id": self.block_id, "user_id": self.user_id}
        ).sort("created_at", -1).limit(limit))
        
        # Reverse to get chronological order
        return list(reversed(history))
    
    def _prepare_step_context(self, current_step, initial_input, previous_content, block_type):
        """Prepare context for step content generation"""
        context = f"Topic: \"{initial_input}\"\nBlock Type: {block_type}\n\n"
        
        # Add title and abstract first (priority steps)
        for priority_step in self.priority_steps:
            if priority_step in previous_content:
                context += f"{priority_step.capitalize()}: {previous_content[priority_step]}\n\n"
        
        # Add other previously generated content summaries
        if previous_content:
            context += "Other previously generated content:\n"
            for prev_step, content in previous_content.items():
                if prev_step not in self.priority_steps and prev_step in self.flow_steps:
                    if isinstance(content, (list, dict)):
                        context += f"- {prev_step}: {json.dumps(content, default=str)[:100]}...\n"
                    else:
                        context += f"- {prev_step}: {str(content)[:100]}...\n"
        
        return context
    
    def _get_step_guidelines(self, step):
        """Get specific guidelines for generating content for a step"""
        guidelines = {
            "title": """
            Create a clear, concise title that captures the essence of this concept.
            The title should be memorable and specific.
            Return only the title text without additional explanation.
            """,
            
            "abstract": """
            Write a concise abstract that summarizes the core concept.
            Cover what it is, why it matters, and its potential impact.
            Use clear, professional language without excessive detail.
            Return only the abstract text without headers or additional commentary.
            """,
            
            "stakeholders": """
            Identify key stakeholders relevant to this concept.
            Include individuals, groups, or organizations directly affected or involved.
            Format as a simple list without complex descriptions.
            """,
            
            "tags": """
            Create relevant tags or keywords for this concept.
            These should be specific and relevant to the topic.
            Format as a list of single words or short phrases.
            """,
            
            "assumptions": """
            List key assumptions underlying this concept.
            These should be foundational beliefs or premises.
            Format as short, clear statements.
            """,
            
            "constraints": """
            List key constraints or limitations affecting this concept.
            Format as short, clear statements.
            """,
            
            "risks": """
            List potential risks or challenges.
            Format as short, clear statements.
            """,
            
            "areas": """
            List fields, disciplines, or domains connected to this concept.
            Include a note about the reach (e.g., global, regional).
            """,
            
            "impact": """
            List key impacts or benefits.
            Format as clear statements emphasizing outcomes.
            """,
            
            "connections": """
            List related innovations or concepts.
            Format as a simple list.
            """,
            
            "classifications": """
            Categorize this concept using different classification schemes.
            Examples: innovation type, development stage, complexity level.
            Format as a list with category names and values.
            """,
            
            "think_models": """
            Apply thinking models (SWOT, First Principles, etc.).
            For each model, provide a brief insight related to the concept.
            Format as a list with model names.
            """
        }
        
        return guidelines.get(step, f"Generate appropriate content for {step}")
    
    def _get_previous_content(self, history):
        """Get previously generated content from conversation history"""
        content = {}
        
        # Process history in reverse to get the most recent content first
        for item in reversed(history):
            if item.get("role") == "assistant" and "result" in item:
                result = item["result"]
                
                # Add each step's content to the dictionary, but only if not already present
                for step in self.flow_steps:
                    if step in result and result[step] and step not in content:
                        content[step] = result[step]
        
        return content
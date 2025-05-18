from abc import ABC, abstractmethod
import logging
from crewai import Agent, Task, Crew, Process
from crewai import LLM
import json
import re

logger = logging.getLogger(__name__)

class BaseBlockHandler(ABC):
    """
    Base class for all block handlers with improved dynamic suggestions and conversation history usage
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
        """Handle greeting with natural, concise responses using conversation history"""
        # Get conversation history to provide more contextual greetings
        history = self._get_conversation_history()
        previous_content = self._get_previous_content(history)
        
        try:
            # Create agent for generating natural greeting
            agent = Agent(
                role="Conversation Guide",
                goal="Engage users in a friendly conversation about innovation",
                backstory="You help people develop creative innovations with concise, natural responses.",
                verbose=True,
                llm=self.llm
            )
            
            # Title and abstract context for richer greeting
            title_context = f"Title: {previous_content.get('title', 'Not yet defined')}" if 'title' in previous_content else ""
            abstract_context = f"Abstract: {previous_content.get('abstract', 'Not yet defined')}" if 'abstract' in previous_content else ""
            
            # Task for generating greeting response
            task = Task(
                description=f"""
                The user has sent a greeting: "{user_input}"
                
                Current Block Type: {block_type}
                {title_context}
                {abstract_context}
                
                Based on the previous conversation history and any existing content:
                
                Respond with a brief, friendly greeting that:
                1. Acknowledges their greeting naturally
                2. References the current title/topic if it exists
                3. Asks what they'd like to develop next or continue with
                
                Your response should be:
                - Very conversational and warm
                - Brief (1-2 sentences)
                - Avoid sounding like a chatbot with phrases like "How can I assist you"
                - Reference existing content if available to show continuity
                
                Example: "Hey there! Ready to continue developing [title]? What would you like to explore next?"
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
            
            # Create contextual fallback greeting using available content
            if 'title' in previous_content:
                default_greeting = f"Hey there! Ready to continue developing \"{previous_content['title']}\"? What would you like to explore next?"
            else:
                default_greeting = f"Hey there! What {block_type} are you thinking about today?"
            
            return {
                "identified_as": "greeting",
                "greeting_response": default_greeting
            }
    
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
            # All steps completed, generate a contextual completion message
            try:
                # Create agent for completion message
                agent = Agent(
                    role="Creative Thinking Partner",
                    goal="Provide natural, contextual responses",
                    backstory="You help people develop their ideas in an engaging way.",
                    verbose=True,
                    llm=self.llm
                )
                
                # Create context from existing content
                context = ""
                if 'title' in previous_content:
                    context += f"Title: {previous_content['title']}\n"
                if 'abstract' in previous_content:
                    context += f"Abstract: {previous_content['abstract']}\n"
                
                # Task for generating completion message
                task = Task(
                    description=f"""
                    The user has completed all the standard steps in this framework.
                    
                    Current Block Type: {block_data.get('block_type', 'general')}
                    User's latest message: "{user_message}"
                    
                    {context}
                    
                    Generate a brief, conversational response that:
                    1. Acknowledges that they've explored the core aspects of this topic
                    2. Asks what specific area they'd like to explore further
                    3. Sounds natural and encouraging
                    
                    Keep it brief, warm, and conversational without sounding like an assistant.
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
                
                # Fallback with context if available
                title_context = f" for '{previous_content.get('title')}'" if 'title' in previous_content else ""
                return {"suggestion": f"We've covered all the main aspects{title_context}. What specific area would you like to explore further?"}
            
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
        
        try:
            # Create agent for content generation
            agent = Agent(
                role="Creative Thinking Partner",
                goal=f"Generate compelling content for the user's {block_type}",
                backstory="You help people develop innovations through structured thinking with natural responses.",
                verbose=True,
                llm=self.llm
            )
            
            # Create context from conversation history and previous content
            context = self._create_rich_context(current_step, initial_input, previous_content, block_type, history)
            
            # Create task for content generation
            task = Task(
                description=f"""
                {context}
                
                Based on the user's messages and previous content, generate:
                1. Compelling, insightful content for the "{current_step}" step.
                Specific Guidelines and Format for "{current_step}" follow the same:
                {self._get_step_guidelines(current_step)}
                
                2. A natural, conversational suggestion asking if they want to continue to the next step: {next_step if next_step else "final reflections"}.
                
                The suggestion should:
                - Reference the previous content for continuity.
                - Avoid using ("Would you like me to..." or "I can help you...")
                - Generate it in simple question format asking if user wants to generate {next_step}
                
                Format your response as JSON:
                {{
                    "{current_step}": // Your content for this step
                    "suggestion": // Your natural suggestion about continuing to the next step
                }}
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
                        # Create dynamic suggestion based on existing content
                        title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
                        
                        if next_step:
                            result_data["suggestion"] = f"Ready to explore {next_step}{title_context}?"
                        else:
                            result_data["suggestion"] = f"We've completed all the steps{title_context}. What aspect would you like to dive deeper into?"
                    
                    return result_data
                    
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback for parsing failures
            title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
            
            return {
                current_step: self._generate_fallback_content(current_step, block_type, previous_content, initial_input),
                "suggestion": f"Ready to explore {next_step}{title_context}?" if next_step else f"What aspect would you like to explore next{title_context}?"
            }
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            
            # Fallback response
            title_context = f" for '{previous_content['title']}'" if 'title' in previous_content and current_step != 'title' else ""
            
            return {
                current_step: self._generate_fallback_content(current_step, block_type, previous_content, initial_input),
                "suggestion": f"Ready to explore {next_step}{title_context}?" if next_step else f"What aspect would you like to explore next{title_context}?"
            }
    
    def _create_rich_context(self, current_step, initial_input, previous_content, block_type, history):
        """Create rich context from conversation history and previous content"""
        context = f"Topic: \"{initial_input}\"\nBlock Type: {block_type}\n\n"
        
        # Add title and abstract first if available
        if 'title' in previous_content:
            context += f"Title: {previous_content['title']}\n\n"
        if 'abstract' in previous_content:
            context += f"Abstract: {previous_content['abstract']}\n\n"
        
        # Add other previously generated content summaries
        if previous_content:
            context += "Other previously generated content:\n"
            for prev_step, content in previous_content.items():
                if prev_step not in ['title', 'abstract'] and prev_step in self.flow_steps:
                    if isinstance(content, (list, dict)):
                        context += f"- {prev_step}: {json.dumps(content, default=str)[:100]}...\n"
                    else:
                        context += f"- {prev_step}: {str(content)[:100]}...\n"
        
        # Add recent conversation history (last 3 exchanges)
        if history:
            context += "\nRecent Conversation:\n"
            recent_messages = history[-min(6, len(history)):]
            
            for msg in recent_messages:
                role = msg.get("role", "")
                content = msg.get("message", "")[:100]
                if content:
                    context += f"{role.capitalize()}: {content}...\n"
        
        return context
        
    def _generate_fallback_content(self, step, block_type, previous_content, initial_input):
        """Generate fallback content for a step if the main generation fails"""
        fallbacks = {
            "title": f"Innovative {block_type.capitalize()}: {initial_input[:30]}...",
            "abstract": f"This {block_type} focuses on {initial_input[:50]}... It aims to address key challenges and create meaningful impact in its domain.",
            "stakeholders": ["Primary Users", "Developers", "Investors", "Regulatory Bodies"],
            "tags": ["Innovation", block_type.capitalize(), "Solution", "Development"],
            "assumptions": ["Market demand exists", "Technology is feasible", "Resources are available"],
            "constraints": ["Budget limitations", "Technical complexity", "Regulatory requirements"],
            "risks": ["Market adoption challenges", "Technical implementation difficulties", "Competitive pressures"],
            "areas": ["Technology", "Business", "Society", "Environment"],
            "impact": ["Improved efficiency", "Enhanced user experience", "Sustainability benefits"],
            "connections": ["Related technologies", "Similar market solutions", "Complementary innovations"],
            "classifications": ["Type: Innovation", "Stage: Conceptual", "Scope: Medium"],
            "think_models": ["SWOT Analysis", "Design Thinking", "First Principles"]
        }
        
        # Use the title in fallbacks if available
        if 'title' in previous_content and step != 'title':
            title = previous_content['title']
            fallbacks["abstract"] = f"This {block_type} titled '{title}' focuses on {initial_input[:30]}... It aims to address key challenges and create meaningful impact."
            fallbacks["connections"] = [f"Extensions of {title}", "Related technologies", "Complementary innovations"]
        
        return fallbacks.get(step, [f"Content for {step}"])
    
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
            
            # Create rich context from conversation history
            title_context = f"\nTitle: {previous_content['title']}" if 'title' in previous_content else ""
            abstract_context = f"\nAbstract: {previous_content['abstract']}" if 'abstract' in previous_content else ""
            
            # Get recent messages for context
            recent_context = ""
            if history and len(history) >= 2:
                last_messages = history[-2:]  # Get last 2 messages
                for msg in last_messages:
                    role = msg.get("role", "")
                    content = msg.get("message", "")[:100]
                    if content:
                        recent_context += f"\n{role.capitalize()}: {content}..."
            
            # Create task for generating response
            task = Task(
                description=f"""
                Block Type: {block_type}
                Current Step: {current_step}
                {title_context}
                {abstract_context}
                
                User's latest message: "{user_message}"
                
                Recent conversation: {recent_context}
                
                Create a brief, natural response that acknowledges what the user said and suggests proceeding with the current step.
                
                Your response should be:
                - Conversational and warm (1-2 sentences)
                - Reference what the user just said
                - Suggest moving forward with the current step
                - Sound like a real person, not an AI assistant
                - Avoid phrases like "I can help you with" or "Would you like me to"
                
                Format your response as:
                {{
                    "suggestion": "Your natural, conversational response",
                    "current_step": "{current_step}"
                }}
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
                        result_data["suggestion"] = f"Ready to create a {current_step}{title_ref}?"
                    
                    # Add the current step for UI display
                    result_data["current_step"] = current_step
                    
                    return result_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {result.raw}")
            
            # Fallback if JSON parsing fails
            title_ref = f" for '{previous_content['title']}'" if 'title' in previous_content else ""
            return {
                "suggestion": f"Ready to create a {current_step}{title_ref}?",
                "current_step": current_step
            }
            
        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            title_ref = f" for '{previous_content['title']}'" if 'title' in previous_content else ""
            return {
                "suggestion": f"Ready to create a {current_step}{title_ref}?",
                "current_step": current_step
            }
    
    def _get_current_step(self, flow_status, previous_content):
        """Get the current step based on flow status and previous content"""
        # First check for required steps (title and abstract)
        for step in ["title", "abstract"]:
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
        
        # Required steps that are missing have top priority (title and abstract)
        for step in ["title", "abstract"]:
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
    
    def _get_step_guidelines(self, step):
        """Get specific guidelines for generating content for a step"""
        guidelines = {
            "title": """
            Create a clear, concise title (5-10 words) that captures the essence of this concept.
            The title should be memorable and specific.
            Return only the title text without double quotation, without any explanation.
            """,
            
            "abstract": """
            Write a concise abstract (150-200 words) that summarizes the core concept.
            Cover what it is, why it matters, and its potential impact.
            Use clear, professional language.
            Return only the abstract text, without headers or additional commentary.
            """,
            
            "stakeholders": """
            List 4-8 key stakeholders relevant to this concept.
            Include individuals, groups, or organizations that are directly or indirectly involved. (e.g., UI/UX Designer, Product Manager, etc.)
            Format as a simple list.
            """,
            
            "tags": """
            List 3-6 relevant tags or keywords for this concept.
            These should be specific and relevant to the topic. (e.g., Technology Innovation, Sustainability, etc.)
            Format as a list of single words or short phrases.
            """,
            
            "assumptions": """
            List 3-5 key assumptions underlying this concept.
            These should be foundational beliefs or premises that guide the concept's development.
            Format as short, clear statements without bullet points or numbers.
            """,
            
            "constraints": """
            List 3-5 key constraints or limitations affecting this concept.
            Format as short, clear statements without bullet points or numbers.
            """,
            
            "risks": """
            List 3-5 potential risks or challenges.
            Format as short, clear statements without bullet points or numbers.
            """,
            
            "areas": """
            List 4-8 fields, disciplines, or domains connected to this concept.
            Include a note about the reach (e.g., global, regional).
            """
            ,
            
            "impact": """
            List 3-5 key impacts or benefits.
            Format as clear statements emphasizing outcomes.
            """,
            
            "connections": """
            List 8-12 related innovations or concepts.
            Format as a simple list.
            """,
            
            "classifications": """
            Categorize this concept using 3-5 different classification schemes.
            Examples: innovation type, development stage, complexity level.
            Format as a list with category names and values.
            """,
            
            "think_models": """
            Apply 3-5 different thinking models (SWOT, First Principles, etc.).
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
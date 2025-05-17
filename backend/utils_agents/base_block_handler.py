from abc import ABC, abstractmethod
import logging
from crewai import Agent, Task, Crew, Process
from crewai import LLM
import json
import re

logger = logging.getLogger(__name__)

class BaseBlockHandler(ABC):
    """
    Base class for all block handlers with improved conversational flow
    """
    
    def __init__(self, db, block_id, user_id):
        """
        Initialize the block handler
        
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
        
        # Initialize LLM
        self.llm = LLM(
            model="azure/gpt-4o-mini",
            temperature=0.7
        )
        
        # Standard flow steps for all block types (following chat-flow.txt)
        # Ensure this order is strictly followed
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
        
        # Basic step descriptions for internal use only (not for user-facing suggestions)
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
        """
        Check if the user input is a greeting
        
        Args:
            user_input: User's message
            
        Returns:
            bool: True if the input is a greeting, False otherwise
        """
        greeting_phrases = [
            "hi", "hello", "hey", "greetings", "good morning", "good afternoon", 
            "good evening", "howdy", "what's up", "how are you", "nice to meet you",
            "how's it going", "sup", "yo", "hiya", "hi there", "hello there",
            "hey there", "welcome", "good day", "how do you do", "how's everything"
        ]

        # Clean and normalize input for comparison
        clean_input = user_input.lower().strip()
        
        # Check if the input starts with any greeting phrase or is a greeting phrase
        for phrase in greeting_phrases:
            if clean_input.startswith(phrase) or clean_input == phrase:
                return True
                
        return False
    
    def handle_greeting(self, user_input, block_type):
        """
        Handle greeting from user with more concise, natural responses
        
        Args:
            user_input: User's greeting message
            block_type: Type of the block
            
        Returns:
            dict: Response with greeting
        """
        # Create a specialized agent for greeting responses
        agent = Agent(
            role="Conversation Guide",
            goal="Engage users in a friendly conversation about innovation",
            backstory="You help people develop creative innovations. You're friendly but concise, guiding naturally without being instructional.",
            verbose=True,
            llm=self.llm
        )
        
        # Block-specific contexts to guide the LLM
        block_contexts = {
            "idea": "innovative ideas",
            "problem": "problems that need solving",
            "possibility": "potential solutions",
            "moonshot": "ambitious, transformative results",
            "needs": "requirements to address",
            "opportunity": "promising opportunities",
            "concept": "structured solutions",
            "outcome": "results to achieve",
            "general": "creative thinking"
        }
        
        context = block_contexts.get(block_type, "creative thinking")
        
        # Create task for generating a greeting response
        task = Task(
            description=f"""
            The user has greeted you with: "{user_input}"
            
            You're having a conversation about {context}.
            
            Respond with a brief, friendly greeting that:
            1. Acknowledges their greeting
            2. Asks an open-ended question about {context} they're thinking about
            
            Keep your response VERY concise (1-2 sentences max).
            Don't use bullet points or numbered lists.
            Don't say "I can help you with..." or "Would you like to..." - just ask naturally.
            """,
            agent=agent,
            expected_output="A brief, friendly greeting"
        )
        
        # Execute the task
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            return {
                "identified_as": "greeting",
                "greeting_response": result.raw.strip(),
                "requires_classification": False
            }
        except Exception as e:
            logger.error(f"Error generating greeting response: {str(e)}")
            default_greeting = f"Hey there! What {block_type} are you thinking about today?"
            return {
                "identified_as": "greeting",
                "greeting_response": default_greeting,
                "requires_classification": False
            }
    
    @abstractmethod
    def initialize_block(self, user_input):
        """
        Initialize a new block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with suggestion for next step
        """
        pass
    
    def process_message(self, user_message, flow_status):
        """
        Process a user message based on current flow status
        Using more concise, conversational transitions between steps
        
        Args:
            user_message: Message from the user
            flow_status: Current flow status
            
        Returns:
            dict: Response with results and next step suggestion
        """
        # Get conversation history (limit to last 10 messages)
        history = self._get_conversation_history(limit=10)
        
        # Check if the message is a greeting
        if self.is_greeting(user_message):
            block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
            block_type = block_data.get("block_type", "general")
            return self.handle_greeting(user_message, block_type)
        
        # Determine if user is confirming to proceed with current step
        # This matches the chat flow where any confirmation ("ok", "yes", etc.) moves to the next step
        is_confirmation = self._is_user_confirmation(user_message)
        
        # Find the current step based on flow status
        current_step = self._get_current_step(flow_status)
        
        if not current_step:
            return {"suggestion": "We've covered all the main aspects. What would you like to explore next?"}
            
        if is_confirmation:
            # User confirms to proceed - generate content for current step
            result = self._generate_step_content(current_step, user_message, flow_status, history)
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Get next step
            next_step = self._get_next_step(updated_flow_status)
            
            # Generate a dynamic suggestion for the next step
            suggestion = self._generate_next_step_suggestion(current_step, next_step)
            
            # Prepare response with formatted content
            content = result if isinstance(result, dict) else self._format_step_content(current_step, result)
            
            # Prepare response with suggestion included in JSON format
            response = {
                current_step: content,
                "suggestion": suggestion,
                "updated_flow_status": updated_flow_status
            }
            
            return response
        else:
            # User provided content or other input - respond contextually
            return self._generate_contextual_response(user_message, current_step, flow_status, history)
    
    def _generate_next_step_suggestion(self, current_step, next_step):
        """
        Generate a dynamic suggestion for the next step - simplified for JSON response
        
        Args:
            current_step: The step that was just completed
            next_step: The next step to suggest
            
        Returns:
            str: A dynamically generated suggestion
        """
        # If there is no next step, return a completion message
        if not next_step:
            return "Great! We've completed all the steps. What would you like to explore further?"
        
        # Simple suggestion template to maintain consistency
        step_action_prompts = {
            "title": "generate a title",
            "abstract": "create an abstract",
            "stakeholders": "identify the stakeholders",
            "tags": "add tags and categories",
            "assumptions": "list the assumptions",
            "constraints": "identify any constraints",
            "risks": "what risks might exist",
            "areas": "explore related areas",
            "impact": "describe the potential impact",
            "connections": "discover connections to other ideas",
            "classifications": "classify this concept",
            "think_models": "apply thinking models"
        }
        
        prompt = step_action_prompts.get(next_step, f"work on the {next_step}")
        return f"Would you like to {prompt}?"
    
    def _is_user_confirmation(self, message):
        """
        Check if the user message is a confirmation to proceed
        Matches any affirmative response like "ok", "yes", "sure", "proceed", etc.
        
        Args:
            message: User's message
            
        Returns:
            bool: True if it's a confirmation, False otherwise
        """
        message = message.lower().strip()
        
        # Common confirmation phrases
        confirmation_phrases = [
            "ok", "okay", "yes", "yeah", "yep", "sure", "proceed", 
            "let's do it", "go ahead", "continue", "generate", "please do",
            "sounds good", "good", "great", "perfect", "do it",
            "i'm ready", "ready", "let's go", "go for it", "next"
        ]
        
        # Check for exact matches for very short inputs
        if message in confirmation_phrases:
            return True
            
        # Check if message starts with or contains confirmation phrases
        for phrase in confirmation_phrases:
            if message.startswith(phrase) or f" {phrase} " in f" {message} ":
                return True
                
        return False
    
    def _format_step_content(self, step, content):
        """Format content based on the step type for standardized presentation"""
        if step == "title":
            return f"{content}"
        elif step == "abstract":
            return f"{content}"
        else:
            # For structured data, leave as is
            return content
    
    def _generate_step_content(self, step, user_message, flow_status, history):
        """
        Generate content for the current step
        
        Args:
            step: Current step in the flow
            user_message: User's message
            flow_status: Current flow status
            history: Conversation history
            
        Returns:
            Content for the current step
        """
        # Get the initial input from the flow data
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        block_type = block_data.get("block_type", "general")
        
        # Get previously generated content
        previous_content = self._get_previous_content(history)
        
        # Create agent for content generation
        agent = Agent(
            role="Creative Thinking Partner",
            goal=f"Generate {self.step_descriptions.get(step, step)} for the user's {block_type}",
            backstory="You help people develop innovations through structured thinking without being verbose.",
            verbose=True,
            llm=self.llm
        )
        
        # Prepare prompt context
        context = self._prepare_step_context(step, initial_input, previous_content, block_type)
        
        # Create task for content generation
        task = Task(
            description=f"""
            {context}
            
            Generate {self.step_descriptions.get(step, step)} for this {block_type}.
            
            Guidelines for "{step}":
            {self._get_step_guidelines(step)}
            
            Make your response:
            - Clear and focused
            - Relevant to the topic
            - Following the specified format
            - NO explanations or commentary
            
            Generate ONLY the content for {step}, nothing more.
            """,
            agent=agent,
            expected_output=f"Content for {step}"
        )
        
        # Execute task
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            return self._parse_step_result(step, result.raw)
        except Exception as e:
            logger.error(f"Error generating content for {step}: {str(e)}")
            return f"I'm having trouble generating {self.step_descriptions.get(step, step)}. Let's try a different approach."
    
    def _prepare_step_context(self, step, initial_input, previous_content, block_type):
        """Prepare context for step content generation"""
        context = f"Topic: \"{initial_input}\"\nBlock Type: {block_type}\n\n"
        
        # Add previously generated content
        if previous_content:
            context += "Previously generated content:\n"
            for prev_step, content in previous_content.items():
                if prev_step in self.flow_steps:
                    if isinstance(content, (dict, list)):
                        context += f"- {prev_step}: {json.dumps(content, ensure_ascii=False)[:100]}...\n"
                    else:
                        context += f"- {prev_step}: {str(content)[:100]}...\n"
        
        return context
    
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
    
    def _parse_step_result(self, step, raw_result):
        """Parse the result based on the step type"""
        # For structured data steps, try to extract JSON if present
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
                    
            # If JSON parsing fails or no JSON found, return formatted list
            return self._format_bullet_list(raw_result)
        else:
            # For title and abstract, return as plain text
            return raw_result.strip()
    
    def _format_bullet_list(self, text):
        """Format text as a bullet list if it contains bullet points"""
        # Split by lines
        lines = text.strip().split('\n')
        formatted_lines = []
        
        for line in lines:
            # Clean up bullet points for consistency
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
        """
        Generate a contextual response for user input that's not a direct confirmation
        With more concise, conversational style
        
        Args:
            user_message: User's message
            current_step: Current step in the flow
            flow_status: Current flow status
            history: Conversation history
            
        Returns:
            dict: Response with suggestion
        """
        # Get the initial input
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        block_type = block_data.get("block_type", "general")
        
        # Create an agent for contextual responses
        agent = Agent(
            role="Conversation Guide",
            goal="Guide users through the creative thinking process",
            backstory="You help users develop innovations with concise, clear responses.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for generating a response
        task = Task(
            description=f"""
            Topic: "{initial_input}"
            Block Type: {block_type}
            Current Step: {current_step} ({self.step_descriptions.get(current_step, current_step)})
            
            Recent conversation:
            {self._format_history_for_prompt(history)}
            
            User's latest message: "{user_message}"
            
            Create a brief, natural response that:
            - Is conversational, 1-2 sentences maximum
            - Suggests generating content for the current step ({current_step})
            - Asks if they'd like to proceed (without being wordy)
            - Uses NO bullet points or numbered lists
            - Uses NO explanations or justifications
            - NEVER explains what you're doing or what will happen next
            """,
            agent=agent,
            expected_output="A brief contextual response"
        )
        
        # Execute the task
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Extract any potential updated status or step suggestion from the response
            is_related_to_current_step = self._is_related_to_current_step(user_message, current_step, initial_input)
            
            if is_related_to_current_step:
                # If user's message is related to current step, guide them to continue
                suggestion = result.raw.strip()
            else:
                # If not related, use the generated response
                suggestion = result.raw.strip()
            
            return {
                "suggestion": suggestion
            }
        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            return {
                "suggestion": f"Would you like to {self.step_descriptions.get(current_step, current_step)}?"
            }
    
    def _is_related_to_current_step(self, user_message, current_step, initial_input):
        """Simple check if user message seems related to current step"""
        step_keywords = {
            "title": ["title", "name", "heading", "call it"],
            "abstract": ["abstract", "summary", "overview", "describe"],
            "stakeholders": ["stakeholders", "people", "users", "groups", "involved"],
            "tags": ["tags", "keywords", "categories", "label", "type"],
            "assumptions": ["assumptions", "assume", "premise", "presuppose"],
            "constraints": ["constraints", "limitations", "restrictions", "limits"],
            "risks": ["risks", "problems", "challenges", "issues", "concerns"],
            "areas": ["areas", "domains", "fields", "subjects", "related to"],
            "impact": ["impact", "effects", "benefits", "results", "outcomes"],
            "connections": ["connections", "links", "related", "similar", "connected"],
            "classifications": ["classifications", "categories", "types", "classes"],
            "think_models": ["thinking", "models", "frameworks", "approaches", "perspectives"]
        }
        
        # Get keywords for current step
        current_keywords = step_keywords.get(current_step, [current_step])
        
        # Check if any keyword appears in the user message
        for keyword in current_keywords:
            if keyword in user_message.lower():
                return True
        
        return False

    def _get_current_step(self, flow_status):
        """Get the current step based on flow status - strictly following the order"""
        # Ensure we're following the exact order defined in self.flow_steps
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
        return None
    
    def _get_next_step(self, flow_status):
        """Get the next step after the current one - strictly following the order"""
        current_step = None
        next_step = None
        
        # Find the current step
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                current_step = step
                break
        
        if current_step is None:
            return None  # All steps completed
        
        # Find the next step
        found_current = False
        for step in self.flow_steps:
            if found_current and not flow_status.get(step, False):
                next_step = step
                break
            if step == current_step:
                found_current = True
                
        return next_step
    
    def _get_conversation_history(self, limit=10):
        """
        Get the conversation history for context
        
        Args:
            limit: Maximum number of messages to retrieve
        """
        history = list(self.history_collection.find(
            {"block_id": self.block_id, "user_id": self.user_id}
        ).sort("created_at", -1).limit(limit))
        
        # Reverse to get chronological order
        return list(reversed(history))
    
    def _format_history_for_prompt(self, history):
        """Format conversation history for inclusion in prompts"""
        formatted = []
        for msg in history:
            role = msg.get("role", "").upper()
            content = msg.get("message", "")
            if role and content:
                formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted[-5:])  # Only use last 5 for prompt context
    
    def _get_previous_content(self, history):
        """Extract previously generated content from history"""
        content = {}
        
        for item in history:
            if item.get("role") == "assistant" and "result" in item:
                result = item["result"]
                
                # Add each step's content to the dictionary
                for step in self.flow_steps:
                    if step in result:
                        content[step] = result[step]
        
        return content
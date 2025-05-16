from abc import ABC, abstractmethod
import logging
from crewai import Agent, Task, Crew, Process
from crewai import LLM

logger = logging.getLogger(__name__)

class BaseBlockHandler(ABC):
    """
    Base class for all block handlers
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
        
        # Steps in the ideal flow order - maintained but not explicitly shown to users
        self.flow_steps = [
            "title",
            "abstract",
            "stakeholders",
            "tags",
            "assumptions",
            "constraints",
            "risks",
            "aspects_implications",
            "impact",
            "connections",
            "classifications",
            "think_models"
        ]
    
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

        """
        UPDATE THE CODE WITH THE FOLLOWING CHANGES:
        1. NEED TO BE CONVERSATIONAL INSTED OF GIVING FOLLOW UP MESSAGES HARDCODED I WANT TO GENERATE THEM ALONG WITH THE LLM MESSAGE TO THE USER RESPONSE DURING THE NORMAL SUGGESTION GENERATION, I DONT NEED ANY HARDCOARDED MESSAGES 
        2. WRITE PROMPTS IN SUCH A WAY THAT TO AVOID HALLUCATION AND GENERATE THINGS IN A CONVERSATIONAL WAY INSTED OF DISPLYING ANY HARDCOARDED MESSAGES
        3. MAKE THE CODE FLEXIBLE TO HANDLE ANY KIND OF RESPONSE SHOULD ANALZYSE BEFORE GENERATING THE RESPONSE
        4. MAKE THE PROPER LOADING OF THE CHAT MESSAGE SINCE THEY ARE NOT LOADING ONCE THE PAGE IS REFRESHED OR LOADED AGAIN IT WILL JUST SHOW EMPTY BUBBLES, I WANT YOU TO MAKE SURE TO MAP THE CONVERSRATION HISTORY
        5. DONT CHANGE ANY OTHER THING OR DONT REMOVE ANYTHING FROM THE CODE JUST MAKE SURE TO KEEP THE THINGS IN THE SAME WAY AS THEY ARE AND JUST ADD THE THINGS THAT I HAVE MENTIONED ABOVE
        """
        
        # Clean and normalize input for comparison
        clean_input = user_input.lower().strip()
        
        # Check if the input starts with any greeting phrase or is a greeting phrase
        for phrase in greeting_phrases:
            if clean_input.startswith(phrase) or clean_input == phrase:
                return True
                
        return False
    
    def handle_greeting(self, user_input, block_type):
        """
        Handle greeting from user
        
        Args:
            user_input: User's greeting message
            block_type: Type of the block
            
        Returns:
            dict: Response with greeting and prompt for ideas
        """
        # Create a specialized agent for greeting responses
        agent = Agent(
            role="Conversation Guide",
            goal="Engage users in a friendly conversation about innovation",
            backstory="You are a helpful assistant for creative thinking. You're friendly, conversational, and naturally guide people without being overly instructional.",
            verbose=True,
            llm=self.llm
        )
        
        # Block-specific prompts made more conversational
        prompts = {
            "idea": "What innovative idea are you thinking about?",
            "problem": "What problem are you looking to solve?",
            "possibility": "What kind of possibility interests you?",
            "moonshot": "Tell me about that big, bold idea you're considering.",
            "needs": "What needs are you focused on addressing?",
            "opportunity": "What opportunity have you spotted?",
            "concept": "What concept would you like to develop further?",
            "outcome": "What outcome are you hoping to achieve?",
            "general": "What's on your mind today?"
        }
        
        # Create task for generating a greeting response
        task = Task(
            description=f"""
            The user has greeted you with: "{user_input}"
            
            You're having a conversation about {block_type}s.
            
            Respond with a friendly greeting that:
            1. Acknowledges their greeting
            2. Briefly explains you can help with {block_type}s
            3. Asks an open-ended question: {prompts.get(block_type, "What's on your mind today?")}
            
            Keep your response conversational, friendly, and concise (2-3 sentences).
            Don't use bullet points, numbered lists, or markdown.
            Avoid phrases like "I can help you with..." or "Would you like to..." - just ask naturally.
            """,
            agent=agent,
            expected_output="A friendly conversational greeting"
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
        
        # Check response type
        response_type = self._analyze_user_response(user_message)
        
        # Find the current step based on flow status
        current_step = self._get_current_step(flow_status)
        
        if not current_step:
            return {"suggestion": "Is there anything else you'd like to explore about this?"}
            
        if response_type == "affirmative":
            # Generate the requested content
            result = self._generate_content(current_step, user_message, flow_status, history)
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Get next step
            next_step = self._get_next_step(updated_flow_status)
            
            # Create more natural follow-up questions based on next step
            follow_ups = {
                "title": "How about we give this a clear title?",
                "abstract": "Can you tell me more about the core idea?",
                "stakeholders": "Who do you think would be involved or affected by this?",
                "tags": "What key themes or categories would you associate with this?",
                "assumptions": "What assumptions are we making here?",
                "constraints": "What limitations or constraints should we consider?",
                "risks": "Are there any potential risks we should think about?",
                "aspects_implications": "How might this affect different areas?",
                "impact": "What impact do you think this might have?",
                "connections": "How does this connect to other ideas or systems?",
                "classifications": "How would you categorize or classify this?",
                "think_models": "Let's look at this from different perspectives. Any thoughts?"
            }
            
            if next_step:
                suggestion = follow_ups.get(next_step, f"What about the {next_step.replace('_', ' ')}?")
            else:
                suggestion = "That covers the main points! Any other aspects you'd like to explore?"
            
            # Prepare response
            response = {
                current_step: result,
                "suggestion": suggestion,
                "updated_flow_status": updated_flow_status
            }
            
            return response
            
        elif response_type == "skip":
            # User wants to skip the current step
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Get next step
            next_step = self._get_next_step(updated_flow_status)
            
            follow_ups = {
                "title": "Let's give this a clear title instead?",
                "abstract": "How about describing the core idea?",
                "stakeholders": "Who do you think would be involved here?",
                "tags": "What key themes would you associate with this?",
                "assumptions": "What assumptions might we be making?",
                "constraints": "Are there any limitations we should think about?",
                "risks": "Any potential risks to consider?",
                "aspects_implications": "How might this affect different areas?",
                "impact": "What kind of impact could this have?",
                "connections": "How does this connect to other ideas?",
                "classifications": "How would you categorize this?",
                "think_models": "Let's look at this from different angles. Thoughts?"
            }
            
            if next_step:
                suggestion = follow_ups.get(next_step, f"Let's talk about the {next_step.replace('_', ' ')} instead.")
            else:
                suggestion = "No problem. What else would you like to discuss about this?"
            
            response = {
                "suggestion": suggestion,
                "updated_flow_status": updated_flow_status
            }
            
            return response
            
        elif response_type == "negative":
            # User doesn't want to continue with the flow
            suggestion = "No problem. What aspects of this would you prefer to focus on?"
            
            return {
                "suggestion": suggestion
            }
            
        elif response_type == "question":
            # Handle user questions about the process
            return self._handle_process_question(user_message, current_step, history)
            
        else:  # "other" - user is talking about something unrelated or giving open input
            # Generate a contextual response using LLM
            response = self._generate_contextual_response(user_message, current_step, flow_status, history)
            
            return {
                "suggestion": response
            }
    
    def _analyze_user_response(self, message):
        """
        Analyze the user's response to determine their intent
        
        Args:
            message: User's message
            
        Returns:
            str: Response type ('affirmative', 'negative', 'skip', 'question', 'other')
        """
        message = message.lower().strip()
        
        # Affirmative responses
        affirmative_phrases = [
            "yes", "yeah", "yep", "sure", "ok", "okay", "proceed", 
            "let's do it", "go ahead", "continue", "generate", "please do"
        ]
        
        # Negative responses
        negative_phrases = [
            "no", "nope", "not now", "i don't want", "don't", "stop", 
            "let's not", "i don't think so", "negative", "pass"
        ]
        
        # Skip responses
        skip_phrases = [
            "skip", "move on", "next", "skip this", "jump to next", 
            "let's skip", "go to next", "bypass", "skip this step"
        ]
        
        # Question indicators
        question_indicators = [
            "what is", "how does", "why do", "can you explain", "tell me about",
            "what does", "how do", "?", "what are", "explain"
        ]
        
        # Check for affirmative responses
        for phrase in affirmative_phrases:
            if phrase in message:
                return "affirmative"
                
        # Check for skip requests
        for phrase in skip_phrases:
            if phrase in message:
                return "skip"
                
        # Check for negative responses
        for phrase in negative_phrases:
            if phrase in message:
                return "negative"
                
        # Check for questions
        for indicator in question_indicators:
            if indicator in message:
                return "question"
                
        # If none of the above, classify as "other"
        return "other"
    
    def _handle_process_question(self, user_message, current_step, history):
        """
        Handle questions about the process
        
        Args:
            user_message: User's question
            current_step: Current step in the flow
            history: Conversation history
            
        Returns:
            dict: Response with explanation
        """
        # Create a specialized agent for answering process questions
        agent = Agent(
            role="Conversation Guide",
            goal="Help users understand the creative thinking process clearly",
            backstory="You're a friendly guide who helps people understand creative thinking in a natural way. You avoid formal language, bullet points, or explicit instructions.",
            verbose=True,
            llm=self.llm
        )
        
        # Convert steps to natural language
        step_descriptions = {
            "title": "giving your idea a clear name",
            "abstract": "summarizing the core concept",
            "stakeholders": "thinking about who would be involved or affected",
            "tags": "identifying key themes or categories",
            "assumptions": "recognizing what assumptions we're making",
            "constraints": "understanding limitations or constraints",
            "risks": "considering potential risks",
            "aspects_implications": "exploring different aspects and implications",
            "impact": "considering the potential impact",
            "connections": "finding connections to other ideas or systems",
            "classifications": "categorizing the idea",
            "think_models": "looking at different thinking perspectives"
        }
        
        current_step_desc = step_descriptions.get(current_step, current_step.replace("_", " "))
        
        # Create task for answering the question
        task = Task(
            description=f"""
            The user has asked a question:
            "{user_message}"
            
            You're currently talking about {current_step_desc}.
            
            Conversation history (last few messages):
            {self._format_history_for_prompt(history)}
            
            Give a helpful, conversational explanation that:
            - Answers their question directly and naturally
            - Uses everyday language, not technical jargon
            - Avoids bullet points, numbers, or explicit instructions
            - Ends with a natural question that continues the conversation
            - Is helpful but brief (2-4 sentences)
            
            Your explanation should NOT include phrases like:
            - "Would you like to..."
            - "The next step is..."
            - "We are currently at the step of..."
            - "Let me explain the process..."
            
            Instead, just answer naturally as in a normal conversation.
            """,
            agent=agent,
            expected_output="A natural conversational response"
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
            return {"suggestion": result.raw.strip()}
        except Exception as e:
            logger.error(f"Error handling process question: {str(e)}")
            return {"suggestion": f"I think we were talking about {current_step_desc}. What are your thoughts on that?"}
    
    def _generate_contextual_response(self, user_message, current_step, flow_status, history):
        """
        Generate a contextual response for an unstructured user message that's more conversational
        
        Args:
            user_message: User's message
            current_step: Current step in the flow
            flow_status: Current flow status
            history: Conversation history
            
        Returns:
            str: Contextual response that guides back to the flow
        """
        # Get the initial input
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        
        # Create an agent for contextual responses
        agent = Agent(
            role="Conversation Guide",
            goal="Keep conversations natural and engaging",
            backstory="You're a thoughtful conversation partner who helps develop ideas naturally. You respond to what people say and gently guide the conversation without being pushy.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for generating a response
        task = Task(
            description=f"""
            Here's what the conversation is about: "{initial_input}"
            
            Recent conversation:
            {self._format_history_for_prompt(history)}
            
            User's latest message: "{user_message}"
            
            Create a helpful response that:
            - Directly addresses what they've just said
            - Feels like a natural conversation between two people
            - Includes an appropriate follow-up question based on their message
            - Is brief (2-3 sentences)
            
            IMPORTANT:
            - Don't use phrases like "the next step", "would you like to", or "shall we continue"
            - Don't mention any "process", "framework", or "steps"
            - Don't use bullet points, formatting or markdown
            - Keep the tone casual but professional
            - Don't use pre-defined responses, make it sound natural and unique
            - Don't mention that you're an AI or that you're generating a response
            - Just respond as a human conversation partner would
            """,
            agent=agent,
            expected_output="A conversational response"
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
            return result.raw.strip()
        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            # Even our fallback should be conversational
            return f"I see what you mean. What else is on your mind about this?"

    def _get_current_step(self, flow_status):
        """Get the current step based on flow status"""
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
        return None
    
    def _get_next_step(self, flow_status):
        """Get the next step after the current one"""
        current_found = False
        
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
                
        return None
    
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
    
    def _generate_content(self, step, user_message, flow_status, history):
        """
        Generate content for a specific step
        
        Args:
            step: Current step to generate
            user_message: User's message
            flow_status: Current flow status
            history: Conversation history
            
        Returns:
            str or dict: Generated content
        """
        # Get the initial input and previous content
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        
        # Get previously generated content for context
        previous_content = self._get_previous_content(history)
        
        # Create a specialized agent for this step
        agent = self._create_agent_for_step(step)
        
        # Create task with context
        task = Task(
            description=self._get_task_description(step, initial_input, previous_content, user_message, history),
            agent=agent,
            expected_output=f"Generated {step} content"
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
            
            # Parse the result based on step type
            return self._parse_result(step, result.raw)
        except Exception as e:
            logger.error(f"Error generating content for {step}: {str(e)}")
            return f"I'm having trouble with this. Maybe we can approach it differently?"
    
    def _create_agent_for_step(self, step):
        """Create a specialized agent for a specific step"""
        step_descriptions = {
            "title": "creating concise, compelling titles",
            "abstract": "summarizing complex concepts clearly",
            "stakeholders": "identifying relevant people and groups",
            "tags": "categorizing ideas effectively",
            "assumptions": "uncovering hidden assumptions",
            "constraints": "recognizing practical limitations",
            "risks": "analyzing potential problems",
            "aspects_implications": "exploring different angles and consequences",
            "impact": "evaluating potential effects",
            "connections": "finding relationships between ideas",
            "classifications": "organizing concepts into useful categories",
            "think_models": "applying different thinking frameworks"
        }
        
        expertise = step_descriptions.get(step, f"working with {step}")
        
        return Agent(
            role=f"Creative Thinking Guide",
            goal=f"Help develop excellent {step.replace('_', ' ')} content",
            backstory=f"You're an expert in {expertise}. You can quickly understand ideas and help improve them through thoughtful conversation.",
            verbose=True,
            llm=self.llm
        )
    
    def _get_task_description(self, step, initial_input, previous_content, user_message, history):
        """Generate a task description for a specific step"""
        # Base context with initial input
        context = f"Topic/idea: \"{initial_input}\"\n\n"
        
        # Add recent conversation history (limit to last 5 messages for context)
        context += "Recent conversation:\n"
        context += self._format_history_for_prompt(history) + "\n\n"
        
        # Add previously generated content for context
        if previous_content:
            context += "Previously developed content:\n"
            for prev_step, content in previous_content.items():
                if isinstance(content, dict):
                    # For JSON content, add a summary instead of raw JSON
                    summary = f"({len(content)} items)"
                    context += f"{prev_step}: {summary}\n"
                else:
                    context += f"{prev_step}: {content}\n"
        
        # Step-specific instructions in more conversational language
        instructions = {
            "title": """Create a short, memorable title (5-10 words) that captures the essence of this concept.
            Make it specific and clear. Don't use generic phrases.
            Return just the title itself, nothing else.""",
            
            "abstract": """Write a brief summary (150-200 words) that explains what this concept is about.
            Cover what it is, why it matters, and who it's for.
            Use clear language a general audience would understand.
            Return just the summary text.""",
            
            "stakeholders": """Identify 3-5 key people or groups who would care about this concept.
            For each, briefly explain why they would care.
            Format as a JSON array of objects with 'stakeholder' and 'interest' keys.""",
            
            "tags": """Suggest 3-6 keywords or phrases that describe this concept.
            Choose words that would help categorize or find this concept.
            Format as a JSON array of strings.""",
            
            "assumptions": """Identify 3-5 things we're taking for granted for this concept to work.
            These might not be explicitly stated but are necessary for success.
            Format as a JSON array of strings.""",
            
            "constraints": """Identify 3-5 limitations or restrictions that might affect this concept.
            These could be technical, financial, legal, ethical, or practical considerations.
            Format as a JSON array of strings.""",
            
            "risks": """Identify 3-5 potential problems or challenges for this concept.
            For each, suggest a possible way to address or mitigate the risk.
            Format as a JSON array of objects with 'risk' and 'mitigation' keys.""",
            
            "aspects_implications": """Explore 3-5 different angles or dimensions of this concept.
            For each, describe what it might mean or lead to.
            Format as a JSON object with aspect names as keys and implications as values.""",
            
            "impact": """Consider 3-5 areas where this concept could make a difference.
            Rate each area from 1-10 for how significant the impact might be.
            Format as a JSON array of objects with 'dimension' and 'rating' keys.""",
            
            "connections": """Identify 3-5 ways this concept connects to other ideas or fields.
            Explain how they relate to each other.
            Format as a JSON array of objects with 'connection' and 'relationship' keys.""",
            
            "classifications": """Categorize this concept in 2-3 different ways.
            This might include type of innovation, complexity level, or development stage.
            Format as a JSON object with category names as keys and classification values.""",
            
            "think_models": """Apply 3-5 different thinking approaches to this concept.
            Examples: SWOT analysis, First Principles, Six Thinking Hats, etc.
            For each approach, provide a brief insight.
            Format as a JSON object with model names as keys and insights as values."""
        }
        
        task_description = f"""
        {context}
        
        User's message: "{user_message}"
        
        Your task: {instructions.get(step, f"Generate content for {step}")}
        
        Remember: The content should feel natural and helpful, not like a rigid template.
        """
        
        return task_description
    
    def _parse_result(self, step, raw_result):
        """Parse the result based on the step type"""
        import json
        import re
        
        # Steps that should return JSON
        json_steps = [
            "stakeholders", "tags", "assumptions", "constraints", "risks",
            "aspects_implications", "impact", "connections", "classifications", "think_models"
        ]
        
        if step in json_steps:
            # Try to find JSON in the result
            json_match = re.search(r'({.*}|\[.*\])', raw_result, re.DOTALL)
            
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON for {step}: {raw_result}")
                    # Return as string if JSON parsing fails
                    return raw_result.strip()
            else:
                return raw_result.strip()
        else:
            # For non-JSON steps, return the raw text
            return raw_result.strip()
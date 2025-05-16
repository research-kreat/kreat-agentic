from abc import ABC, abstractmethod
import logging
from crewai import Agent, Task, Crew, Process
from crewai import LLM
import json
import re

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
        
        # Block-specific contexts to guide the LLM
        block_contexts = {
            "idea": "innovative ideas and creative concepts",
            "problem": "challenges and problems that need solving",
            "possibility": "exploring potential solutions and approaches",
            "moonshot": "ambitious, transformative ideas",
            "needs": "requirements and goals to address",
            "opportunity": "promising opportunities and potential markets",
            "concept": "structured solutions and frameworks",
            "outcome": "results and end states to achieve",
            "general": "creative thinking and innovation"
        }
        
        context = block_contexts.get(block_type, "creative thinking")
        
        # Create task for generating a greeting response
        task = Task(
            description=f"""
            The user has greeted you with: "{user_input}"
            
            You're having a conversation about {context}.
            
            Respond with a friendly greeting that:
            1. Acknowledges their greeting
            2. Briefly explains you can help with {block_type}s
            3. Asks an open-ended question about what they're thinking about related to {context}
            
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
            # Generate the requested content and follow-up suggestion in one LLM call
            result = self._generate_content_with_followup(current_step, user_message, flow_status, history)
            
            # Extract content and suggestion
            content = result.get("content", "")
            suggestion = result.get("suggestion", "What else would you like to explore?")
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Prepare response
            response = {
                current_step: content,
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
            
            # Generate a dynamic follow-up question about the next step
            suggestion = self._generate_dynamic_followup(next_step, user_message, history)
            
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
    
    def _generate_dynamic_followup(self, next_step, user_message, history):
        """
        Generate a dynamic follow-up question based on the next step
        
        Args:
            next_step: The next step in the flow
            user_message: User's message
            history: Conversation history
            
        Returns:
            str: Dynamic follow-up question
        """
        if not next_step:
            return "No problem. What else would you like to explore about this?"
            
        # Step to natural language description mapping
        step_descriptions = {
            "title": "a name or title",
            "abstract": "the core idea",
            "stakeholders": "who would be involved or affected",
            "tags": "key themes or categories",
            "assumptions": "what we're assuming",
            "constraints": "limitations to consider",
            "risks": "potential challenges",
            "aspects_implications": "different angles or impacts",
            "impact": "the potential effects",
            "connections": "how it connects to other ideas",
            "classifications": "how to categorize this",
            "think_models": "different perspectives or approaches"
        }
        
        step_desc = step_descriptions.get(next_step, next_step.replace("_", " "))
        
        # Create an agent for generating follow-up questions
        agent = Agent(
            role="Conversation Guide",
            goal="Create natural transitions in conversations",
            backstory="You're skilled at guiding conversations in a natural way that doesn't feel forced or scripted.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for generating a follow-up
        task = Task(
            description=f"""
            Recent conversation:
            {self._format_history_for_prompt(history)}
            
            User's latest message: "{user_message}"
            
            You want to naturally guide the conversation toward discussing {step_desc}.
            
            Create a brief (1-2 sentence) response that:
            - Acknowledges their desire to move on
            - Includes a natural question about {step_desc}
            - Feels conversational, not like following a script
            - Avoids phrases like "the next step", "would you like to", or "shall we proceed"
            
            The question should be specific enough to guide them but open-ended enough to allow creativity.
            
            IMPORTANT: 
            - Do NOT use phrases like "Why don't we talk about..."
            - Do NOT mention "steps", "process", or "framework"
            - Do NOT use bullet points, numbering, or markdown
            - Keep it casual and natural, as in a normal conversation
            """,
            agent=agent,
            expected_output="A natural follow-up question"
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
            logger.error(f"Error generating dynamic follow-up: {str(e)}")
            return f"Got it. What about {step_desc}?"

    def _get_current_step(self, flow_status):
        """Get the current step based on flow status"""
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
        return None
    
    def _get_next_step(self, flow_status):
        """Get the next step after the current one"""
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
    
    def _generate_content_with_followup(self, step, user_message, flow_status, history):
        """
        Generate both content for a specific step and a dynamic follow-up in a single LLM call
        
        Args:
            step: Current step to generate
            user_message: User's message
            flow_status: Current flow status
            history: Conversation history
            
        Returns:
            dict: Generated content and follow-up suggestion
        """
        # Get the initial input and previous content
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        
        # Get previously generated content for context
        previous_content = self._get_previous_content(history)
        
        # Get the next step
        updated_flow_status = flow_status.copy()
        updated_flow_status[step] = True
        next_step = self._get_next_step(updated_flow_status)
        
        # Step descriptions for context
        step_descriptions = {
            "title": "a concise, compelling title",
            "abstract": "a clear summary of the core concept",
            "stakeholders": "people or groups who would be involved or affected",
            "tags": "key themes or categories",
            "assumptions": "things we're taking for granted",
            "constraints": "limitations or restrictions",
            "risks": "potential problems or challenges",
            "aspects_implications": "different angles or dimensions",
            "impact": "areas where this could make a difference",
            "connections": "relationships to other ideas or fields",
            "classifications": "ways to categorize this concept",
            "think_models": "different thinking approaches or frameworks"
        }
        
        next_step_desc = step_descriptions.get(next_step, next_step.replace("_", " ")) if next_step else "other aspects"
        
        # Create a specialized agent
        agent = Agent(
            role="Creative Thinking Partner",
            goal="Develop ideas naturally through conversation",
            backstory="You help people refine their ideas through thoughtful dialogue. You balance between structure and natural conversation.",
            verbose=True,
            llm=self.llm
        )
        
        # Content generation formats
        content_format_instructions = {
            "title": "Create a short, memorable title (5-10 words).",
            "abstract": "Write a brief summary (150-200 words).",
            "stakeholders": "Identify 3-5 key people or groups as a JSON array of objects with 'stakeholder' and 'interest' keys.",
            "tags": "Suggest 3-6 keywords as a JSON array of strings.",
            "assumptions": "Identify 3-5 assumptions as a JSON array of strings.",
            "constraints": "Identify 3-5 limitations as a JSON array of strings.",
            "risks": "Identify 3-5 potential problems as a JSON array of objects with 'risk' and 'mitigation' keys.",
            "aspects_implications": "Explore 3-5 different angles as a JSON object with aspect names as keys and implications as values.",
            "impact": "Consider 3-5 impact areas as a JSON array of objects with 'dimension' and 'rating' keys.",
            "connections": "Identify 3-5 connections as a JSON array of objects with 'connection' and 'relationship' keys.",
            "classifications": "Categorize in 2-3 different ways as a JSON object with category names as keys and classification values.",
            "think_models": "Apply 3-5 different thinking approaches as a JSON object with model names as keys and insights as values."
        }
        
        format_instruction = content_format_instructions.get(step, f"Generate content for {step}")
        
        # Create task
        task = Task(
            description=f"""
            Topic/idea: "{initial_input}"
            
            Recent conversation:
            {self._format_history_for_prompt(history)}
            
            User's message: "{user_message}"
            
            Your task has TWO parts:
            
            PART 1: Generate content about {step_descriptions.get(step, step.replace("_", " "))}
            {format_instruction}
            
            PART 2: Create a natural follow-up question about {next_step_desc}
            This should be a single, conversational sentence that flows naturally from your response above.
            Don't use phrases like "the next step", "would you like to", or mention any process or framework.
            Just ask a natural question as one person would ask another in conversation.
            
            Format your response as a JSON object with two keys:
            - "content": your generated content for {step}
            - "suggestion": your natural follow-up question about {next_step_desc}
            
            For example:
            {{
              "content": "your generated content here",
              "suggestion": "your natural follow-up question here"
            }}
            """,
            agent=agent,
            expected_output="A JSON with content and follow-up question"
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
            
            # Try to parse the result as JSON
            try:
                # Find JSON pattern in the result
                json_match = re.search(r'({.*})', result.raw, re.DOTALL)
                if json_match:
                    result_json = json.loads(json_match.group(1))
                    
                    # Parse content based on step type
                    content = result_json.get("content", "")
                    if step in ["stakeholders", "tags", "assumptions", "constraints", "risks", 
                               "aspects_implications", "impact", "connections", "classifications", "think_models"]:
                        # Try to parse as JSON if it's a JSON string
                        if isinstance(content, str) and (content.startswith('{') or content.startswith('[')):
                            try:
                                content = json.loads(content)
                            except:
                                pass
                    
                    return {
                        "content": content,
                        "suggestion": result_json.get("suggestion", "What else would you like to explore?")
                    }
                else:
                    logger.error(f"No JSON found in result: {result.raw}")
                    return {
                        "content": result.raw.strip(),
                        "suggestion": "What other aspects would you like to discuss?"
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return {
                    "content": result.raw.strip(),
                    "suggestion": "What do you think about this? Any aspects you'd like to explore further?"
                }
                
        except Exception as e:
            logger.error(f"Error generating content with follow-up: {str(e)}")
            return {
                "content": "I'm having trouble with this. Maybe we can approach it differently?",
                "suggestion": "What aspects of this are most important to you?"
            }
    
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
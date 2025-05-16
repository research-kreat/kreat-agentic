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
        
        # Steps in the ideal flow order
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
            backstory="You are a helpful assistant specialized in the KRAFT framework. You greet users warmly and guide them to share their ideas or problems.",
            verbose=True,
            llm=self.llm
        )
        
        # Block-specific prompts
        prompts = {
            "idea": "Share an innovative idea you'd like to develop",
            "problem": "Describe a problem you'd like to solve",
            "possibility": "Share a possibility you'd like to explore",
            "moonshot": "Share an ambitious, transformative idea",
            "needs": "Describe some needs you'd like to address",
            "opportunity": "Share an opportunity you'd like to explore",
            "concept": "Describe a concept you'd like to develop",
            "outcome": "Share an outcome you'd like to achieve",
            "general": "Share what's on your mind and I'll help classify it"
        }
        
        # Create task for generating a greeting response
        task = Task(
            description=f"""
            The user has greeted you with: "{user_input}"
            
            You're working with the {block_type} block in the KRAFT framework.
            
            Respond with a friendly greeting that:
            1. Acknowledges their greeting
            2. Briefly explains what this {block_type} block can help them with
            3. Encourages them to {prompts.get(block_type, "share their thoughts")}
            
            Keep your response conversational, friendly, and concise (3-4 sentences).
            """,
            agent=agent,
            expected_output="A friendly greeting response"
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
            default_greeting = f"Hello! I'm your {block_type.capitalize()} assistant. How can I help you today?"
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
            return {"suggestion": "All steps have been completed for this block. Is there anything else you'd like to discuss?"}
            
        if response_type == "affirmative":
            # Generate the requested content
            result = self._generate_content(current_step, user_message, flow_status)
            
            # Update flow status
            updated_flow_status = flow_status.copy()
            updated_flow_status[current_step] = True
            
            # Get next step
            next_step = self._get_next_step(updated_flow_status)
            
            if next_step:
                suggestion = f"Would you like to generate {next_step.replace('_', ' ')} based on this?"
            else:
                suggestion = "All steps have been completed for this block. Is there something specific you'd like to explore next?"
            
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
            
            if next_step:
                suggestion = f"I understand you want to skip this step. Moving on - would you like to generate {next_step.replace('_', ' ')} instead?"
            else:
                suggestion = "I understand you want to skip this step. We've actually completed all the steps for this block. Is there something else you'd like to explore?"
            
            response = {
                "suggestion": suggestion,
                "updated_flow_status": updated_flow_status
            }
            
            return response
            
        elif response_type == "negative":
            # User doesn't want to continue with the flow
            suggestion = f"I understand you don't want to continue with {current_step.replace('_', ' ')} right now. The step is important for a comprehensive analysis, but we can always come back to it. Would you like to discuss something else about this topic, or should we continue with a different approach?"
            
            return {
                "suggestion": suggestion
            }
            
        elif response_type == "question":
            # Handle user questions about the process
            return self._handle_process_question(user_message, current_step)
            
        else:  # "other" - user is talking about something unrelated or giving open input
            # Generate a contextual response using LLM
            response = self._generate_contextual_response(user_message, current_step, flow_status)
            
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
    
    # Rest of the methods remain the same
    def _handle_process_question(self, user_message, current_step):
        """
        Handle questions about the process
        
        Args:
            user_message: User's question
            current_step: Current step in the flow
            
        Returns:
            dict: Response with explanation
        """
        # Create a specialized agent for answering process questions
        agent = Agent(
            role="Process Guide",
            goal="Explain the KRAFT framework process clearly",
            backstory="You are an expert in the KRAFT framework and help users understand the process and methodology.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for answering the question
        task = Task(
            description=f"""
            The user has asked a question about the KRAFT framework process:
            "{user_message}"
            
            They are currently at the "{current_step}" step of the flow.
            
            Provide a helpful, concise explanation that answers their question while encouraging them to continue with the flow.
            Emphasize the value of following the structured approach but be understanding if they want flexibility.
            
            End your response by asking if they want to proceed with the current step ({current_step}).
            """,
            agent=agent,
            expected_output="A helpful explanation and guidance"
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
            return {"suggestion": f"I apologize, but I'm having trouble understanding your question. Let's continue with the {current_step.replace('_', ' ')} step - would you like to proceed?"}
    
    def _generate_contextual_response(self, user_message, current_step, flow_status):
        """
        Generate a contextual response for an unstructured user message
        
        Args:
            user_message: User's message
            current_step: Current step in the flow
            flow_status: Current flow status
            
        Returns:
            str: Contextual response that guides back to the flow
        """
        # Get the initial input and conversation history
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        history = self._get_conversation_history()
        
        # Create an agent for contextual responses
        agent = Agent(
            role="Conversation Guide",
            goal="Keep the conversation focused and productive",
            backstory="You help users stay on track with the KRAFT framework while being responsive to their needs and questions.",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for generating a response
        task = Task(
            description=f"""
            The user is working through the KRAFT framework and is currently at the "{current_step}" step.
            
            Initial input: "{initial_input}"
            
            User's latest message: "{user_message}"
            
            Create a helpful response that:
            1. Acknowledges what the user has said
            2. Provides relevant information or thoughts on their input
            3. Gently guides them back to the current step in the framework
            4. Ends by asking if they want to proceed with generating content for {current_step.replace('_', ' ')}
            
            Maintain a conversational, helpful tone. Be flexible while encouraging the structured approach.
            """,
            agent=agent,
            expected_output="A contextual response that guides back to the framework"
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
            return f"I see. Let's continue with our process - would you like to generate {current_step.replace('_', ' ')} now?"
    
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
    
    def _get_conversation_history(self):
        """Get the conversation history for context"""
        history = list(self.history_collection.find(
            {"block_id": self.block_id, "user_id": self.user_id}
        ).sort("created_at", 1))
        
        return history
    
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
    
    def _generate_content(self, step, user_message, flow_status):
        """
        Generate content for a specific step
        
        Args:
            step: Current step to generate
            user_message: User's message
            flow_status: Current flow status
            
        Returns:
            str or dict: Generated content
        """
        # Get the initial input and previous content
        block_data = self.flow_collection.find_one({"block_id": self.block_id, "user_id": self.user_id})
        initial_input = block_data.get("initial_input", "")
        
        # Get conversation history
        history = self._get_conversation_history()
        
        # Get previously generated content for context
        previous_content = self._get_previous_content(history)
        
        # Create a specialized agent for this step
        agent = self._create_agent_for_step(step)
        
        # Create task with context
        task = Task(
            description=self._get_task_description(step, initial_input, previous_content, user_message),
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
            return f"Sorry, there was an error generating the {step}. Please try again."
    
    def _create_agent_for_step(self, step):
        """Create a specialized agent for a specific step"""
        step_descriptions = {
            "title": "Generate a concise, compelling title for the content",
            "abstract": "Create a comprehensive abstract that summarizes the main points",
            "stakeholders": "Identify the relevant stakeholders who would be affected",
            "tags": "Generate appropriate tags for categorization",
            "assumptions": "Identify key assumptions underlying the concept",
            "constraints": "Define constraints or limitations that might affect implementation",
            "risks": "Analyze potential risks associated with the concept",
            "aspects_implications": "Explore different aspects and their implications",
            "impact": "Assess the potential impact across various dimensions",
            "connections": "Identify connections to other concepts or systems",
            "classifications": "Classify the concept according to relevant taxonomies",
            "think_models": "Apply appropriate thinking models to analyze the concept"
        }
        
        return Agent(
            role=f"{step.capitalize()} Specialist",
            goal=f"Generate high-quality {step} content",
            backstory=f"You are an expert in creating {step} content for concepts. You understand how to distill information into valuable {step} insights.",
            verbose=True,
            llm=self.llm
        )
    
    def _get_task_description(self, step, initial_input, previous_content, user_message):
        """Generate a task description for a specific step"""
        # Base context with initial input
        context = f"Initial input: \"{initial_input}\"\n\n"
        
        # Add previously generated content for context
        if previous_content:
            context += "Previously generated content:\n"
            for prev_step, content in previous_content.items():
                if isinstance(content, dict):
                    context += f"{prev_step.upper()}: {str(content)}\n"
                else:
                    context += f"{prev_step.upper()}: {content}\n"
        
        # Step-specific instructions
        instructions = {
            "title": """Generate a concise, compelling title (max 10 words) that captures the essence of the concept.
            Make it specific, memorable, and professional. Avoid generic phrases.
            Return just the title as plain text, no additional explanation.""",
            
            "abstract": """Create a comprehensive abstract (150-250 words) that summarizes the key aspects of the concept.
            Include: what the concept is, the problem it addresses, target audience/stakeholders, and potential impact.
            Use clear, professional language. Be specific rather than general.
            Return the abstract as plain text.""",
            
            "stakeholders": """Identify 3-7 key stakeholders or user groups who would be affected by or interested in this concept.
            For each, briefly explain their interest or relation to the concept.
            Return as a JSON array of objects with 'stakeholder' and 'interest' keys.""",
            
            "tags": """Generate 3-6 relevant tags that categorize this concept.
            Tags should reflect the domain, purpose, technology, or other relevant attributes.
            Return as a JSON array of tag strings.""",
            
            "assumptions": """Identify 3-5 key assumptions underlying this concept.
            These are things that must be true for the concept to work but might not be explicitly stated.
            Return as a JSON array of assumption strings.""",
            
            "constraints": """Define 3-5 constraints or limitations that might affect implementation of this concept.
            These could be technical, financial, legal, ethical, or practical considerations.
            Return as a JSON array of constraint strings.""",
            
            "risks": """Analyze 3-5 potential risks associated with this concept.
            Include both implementation risks and potential negative outcomes if implemented.
            Return as a JSON array of risk objects with 'risk' and 'mitigation' keys.""",
            
            "aspects_implications": """Explore different aspects of this concept and their implications.
            Consider at least 3 different perspectives (e.g., technical, social, economic).
            Return as a JSON object with aspect names as keys and implication descriptions as values.""",
            
            "impact": """Assess the potential impact of this concept across 3-5 different dimensions.
            These could include social impact, environmental impact, economic impact, etc.
            Rate each dimension from 1-10 for significance.
            Return as a JSON array of impact objects with 'dimension' and 'rating' keys.""",
            
            "connections": """Identify 3-5 connections between this concept and other concepts, systems, or domains.
            Explain how they relate or could be integrated.
            Return as a JSON array of connection objects with 'connection' and 'relationship' keys.""",
            
            "classifications": """Classify this concept according to 2-3 relevant taxonomies.
            These could include innovation type (incremental/disruptive/radical), complexity level, maturity stage, etc.
            Return as a JSON object with taxonomy names as keys and classification values.""",
            
            "think_models": """Apply 3-5 appropriate thinking models to analyze this concept.
            These could include SWOT analysis, Six Thinking Hats, First Principles, etc.
            Provide a brief insight from each model's perspective.
            Return as a JSON object with model names as keys and insights as values."""
        }
        
        task_description = f"""
        {context}
        
        User's message: "{user_message}"
        
        TASK: {instructions.get(step, f"Generate content for {step}")}
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
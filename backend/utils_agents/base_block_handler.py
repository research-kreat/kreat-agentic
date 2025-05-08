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
            model="azure/gpt-4o-mini",  # Use appropriate model
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
        # Check if the user wants to generate the next part
        affirmative_response = self._is_affirmative(user_message)
        
        # Find the current step based on flow status
        current_step = self._get_current_step(flow_status)
        
        if not current_step:
            return {"suggestion": "All steps have been completed for this block."}
            
        if affirmative_response:
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
                suggestion = "All steps have been completed for this block. Is there anything else you'd like to do?"
            
            # Prepare response
            response = {
                current_step: result,
                "suggestion": suggestion,
                "updated_flow_status": updated_flow_status
            }
            
            return response
        else:
            # User declined or sent another message
            suggestion = f"Would you like to generate {current_step.replace('_', ' ')}?"
            
            return {
                "suggestion": suggestion
            }
    
    def _is_affirmative(self, message):
        """Check if the message is an affirmative response"""
        message = message.lower().strip()
        affirmative_phrases = [
            "yes", "yeah", "yep", "sure", "ok", "okay", "proceed", 
            "let's do it", "go ahead", "continue", "generate", "please do"
        ]
        
        for phrase in affirmative_phrases:
            if phrase in message:
                return True
                
        return False
    
    def _get_current_step(self, flow_status):
        """Get the current step based on flow status"""
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                return step
        return None
    
    def _get_next_step(self, flow_status):
        """Get the next step after the current one"""
        found_current = False
        
        for step in self.flow_steps:
            if not flow_status.get(step, False):
                if found_current:
                    return step
                return step
            else:
                found_current = True
                
        return None
    
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
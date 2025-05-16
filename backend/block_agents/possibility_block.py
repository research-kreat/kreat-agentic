from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

class PossibilityBlockHandler(BaseBlockHandler):
    """
    Handler for the Possibility block type
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Possibility block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "possibility")
        
        # Create specialized agent for possibility initialization
        possibility_agent = Agent(
            role="Possibility Explorer",
            goal="Help people explore potential solutions and approaches naturally",
            backstory="""You're a thoughtful conversation partner who helps people explore different possibilities and options. 
            You encourage them to think beyond obvious solutions and consider alternative approaches.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The person has shared this possibility:
            
            "{user_input}"
            
            First, understand what makes this an interesting possibility and what potential it holds.
            
            Then, respond with 2-3 sentences that:
            1. Acknowledge their possibility with genuine interest
            2. Highlight something intriguing or valuable about it
            3. End with a natural question about what they might call this possibility
            
            Keep your response conversational and natural - avoid phrases like "Would you like to...", "The next step is...", or "Let's generate a..."
            
            Don't use markdown, bullet points, or structured formatting.
            """,
            agent=possibility_agent,
            expected_output="Brief analysis and natural follow-up"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[possibility_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Prepare response with suggestion for title
            response = {
                "identified_as": "possibility",
                "analysis": result.raw.strip(),
                "suggestion": result.raw.strip()  # Use the same natural response
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing possibility block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "possibility",
                "analysis": "That's an interesting possibility to explore. What would you call this approach?",
                "suggestion": "That's an interesting possibility to explore. What would you call this approach?"
            }
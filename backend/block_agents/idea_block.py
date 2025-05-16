from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

class IdeaBlockHandler(BaseBlockHandler):
    """
    Handler for the Idea block type
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
            role="Creative Thinking Partner",
            goal="Help people develop innovative ideas naturally",
            backstory="""You're a thoughtful conversation partner who helps people refine their ideas through natural dialogue. 
            You avoid sounding like an instruction manual or process guide.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The person has shared this idea:
            
            "{user_input}"
            
            First, understand what makes this an interesting idea and why it might be valuable.
            
            Then, respond with 2-3 sentences that:
            1. Acknowledge their idea positively
            2. Highlight a potential value or benefit their idea offers
            3. End with a natural question about what they want to call this idea
            
            Keep your response conversational and natural - avoid phrases like "Would you like to...", "The next step is...", or "Let's generate a..."
            
            Don't use markdown, bullet points, or structured formatting.
            """,
            agent=idea_agent,
            expected_output="Brief analysis and natural follow-up"
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
            
            # Prepare response with suggestion for title
            response = {
                "identified_as": "idea",
                "analysis": result.raw.strip(),
                "suggestion": result.raw.strip()
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "analysis": "That's an interesting idea with potential. What would you like to call it?",
                "suggestion": "That's an interesting idea with potential. What would you like to call it?"
            }
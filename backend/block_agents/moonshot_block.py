from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

class MoonshotBlockHandler(BaseBlockHandler):
    """
    Handler for the Moonshot block type - for ambitious, transformative ideas
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Moonshot block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "moonshot")
        
        # Create specialized agent for moonshot initialization
        moonshot_agent = Agent(
            role="Big Idea Explorer",
            goal="Help people develop ambitious, transformative ideas",
            backstory="""You're a visionary thinker who helps people explore ambitious ideas that could transform the future.
            You encourage bold thinking while remaining grounded in possibility. You're enthusiastic about big ideas without being unrealistic.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The person has shared this ambitious idea:
            
            "{user_input}"
            
            First, understand what makes this a potentially transformative idea and why it matters.
            
            Then, respond with 2-3 sentences that:
            1. Show genuine enthusiasm for their ambitious vision
            2. Highlight the transformative potential you see in it
            3. End with a natural question about what they might call this moonshot idea
            
            Keep your response conversational and natural - avoid phrases like "Would you like to...", "The next step is...", or "Let's generate a..."
            
            Don't use markdown, bullet points, or structured formatting.
            """,
            agent=moonshot_agent,
            expected_output="Brief analysis and natural follow-up"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[moonshot_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Prepare response with suggestion for title
            response = {
                "identified_as": "moonshot",
                "analysis": result.raw.strip(),
                "suggestion": result.raw.strip()  # Use the same natural response
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing moonshot block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "moonshot",
                "analysis": "That's an ambitious and potentially transformative idea! What would you call this moonshot vision?",
                "suggestion": "That's an ambitious and potentially transformative idea! What would you call this moonshot vision?"
            }
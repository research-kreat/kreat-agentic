from utils_agents.base_block_handler import BaseBlockHandler
import logging
from crewai import Agent, Task, Crew, Process

logger = logging.getLogger(__name__)

class ProblemBlockHandler(BaseBlockHandler):
    """
    Handler for the Problem block type
    """
    
    def initialize_block(self, user_input):
        """
        Initialize a new Problem block based on user input
        
        Args:
            user_input: Initial user message
            
        Returns:
            dict: Response with classification and suggestion for next step
        """
        # Check if the input is a greeting
        if self.is_greeting(user_input):
            return self.handle_greeting(user_input, "problem")
        
        # Create specialized agent for problem initialization
        problem_agent = Agent(
            role="Problem Exploration Partner",
            goal="Help people clarify and explore challenges naturally",
            backstory="""You're a thoughtful conversation partner who helps people understand their problems more deeply through natural dialogue. 
            You avoid sounding like an instruction manual or process guide.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            The person has shared this problem:
            
            "{user_input}"
            
            First, understand what makes this an important problem and why addressing it would be valuable.
            
            Then, respond with 2-3 sentences that:
            1. Acknowledge the significance of the problem they've identified
            2. Highlight why addressing this problem matters
            3. End with a natural question about what they might call this problem
            
            Keep your response conversational and natural - avoid phrases like "Would you like to...", "The next step is...", or "Let's generate a..."
            
            Don't use markdown, bullet points, or structured formatting.
            """,
            agent=problem_agent,
            expected_output="Brief analysis and natural follow-up"
        )
        
        # Execute the analysis
        crew = Crew(
            agents=[problem_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Prepare response with suggestion for title
            response = {
                "identified_as": "problem",
                "analysis": result.raw.strip(),
                "suggestion": result.raw.strip()  # Use the same natural response
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing problem block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "problem",
                "analysis": "That's a significant challenge worth addressing. What would you call this problem?",
                "suggestion": "That's a significant challenge worth addressing. What would you call this problem?"
            }
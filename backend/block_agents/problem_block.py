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
            role="Problem Framework Specialist",
            goal="Help users define and explore challenges clearly",
            backstory="""You are an expert in problem definition and analysis.
            You help users articulate their challenges clearly and comprehensively,
            enabling better understanding and solution development.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            Analyze the following user input as a problem or challenge:
            
            "{user_input}"
            
            Provide a brief analysis of what makes this a problem worth solving and its potential impact.
            Be encouraging and supportive of the user's focus on this problem.
            
            Your output should be a brief analysis (2-3 sentences) that validates the importance of the problem
            and suggests why addressing it would be valuable.
            """,
            agent=problem_agent,
            expected_output="Brief analysis of the problem's significance"
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
                "suggestion": "Would you like to generate a title for this problem?"
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing problem block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "problem",
                "analysis": "This appears to be an important problem with significant implications worth addressing.",
                "suggestion": "Would you like to generate a title for this problem?"
            }
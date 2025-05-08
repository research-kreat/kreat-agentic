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
        # Create specialized agent for idea initialization
        idea_agent = Agent(
            role="Idea Framework Specialist",
            goal="Help users develop innovative concepts and ideas",
            backstory="""You are an expert in idea development and innovation frameworks.
            You help users take their initial concepts and develop them into well-structured
            and thoughtful ideas with clear titles, abstracts, and supporting details.""",
            verbose=True,
            llm=self.llm
        )
        
        # Create task for initial analysis
        analysis_task = Task(
            description=f"""
            Analyze the following user input as an idea or concept:
            
            "{user_input}"
            
            Provide a brief analysis of what makes this an idea and what potential value it might have.
            Be encouraging and supportive of the user's creativity.
            
            Your output should be a brief analysis (2-3 sentences) that validates the user's idea
            and suggests its potential value or application.
            """,
            agent=idea_agent,
            expected_output="Brief analysis of the idea's potential"
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
                "suggestion": "Would you like to generate a title for this idea?"
            }
            
            return response
        except Exception as e:
            logger.error(f"Error initializing idea block: {str(e)}")
            
            # Fallback response
            return {
                "identified_as": "idea",
                "analysis": "This appears to be an interesting idea with potential value.",
                "suggestion": "Would you like to generate a title for this idea?"
            }
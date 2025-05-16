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
        
        analysis_task = Task(
            description=f"""
            The person has shared this idea:
            
            "{user_input}"
            
            Your goal is to provide a natural, conversational response that:
            1. Shows genuine interest in their idea
            2. Acknowledges something specific from what they shared
            3. Asks a thoughtful follow-up question to explore their idea further
            
            IMPORTANT CONSTRAINTS:
            - Keep your response to 2-3 sentences maximum
            - Write in a casual, conversational tone as if talking to a colleague
            - Don't mention frameworks, processes, or structured approaches
            - Don't use phrases like "would you like to" or "let's proceed to" 
            - Only mention information directly related to what they've shared
            - Don't make any claims that aren't directly supported by their message
            - If you're unsure about details, ask questions rather than making assumptions
            
            Don't use markdown, bullet points, or structured formatting.
            """,
            agent=idea_agent,
            expected_output="Brief, conversational response to their idea"
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
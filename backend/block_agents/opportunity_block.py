from utils_agents.base_block_handler import BaseBlockHandler
import logging

logger = logging.getLogger(__name__)

class OpportunityBlockHandler(BaseBlockHandler):
    """Handler for the Opportunity block type"""
    
    def initialize_block(self, user_input):
        """Initialize a new Opportunity block"""
        return {
            "identified_as": "opportunity",
            "analysis": "This appears to be a valuable opportunity worth exploring.",
            "suggestion": "Would you like to generate a title for this opportunity?"
        }

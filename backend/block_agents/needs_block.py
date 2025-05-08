from utils_agents.base_block_handler import BaseBlockHandler
import logging

logger = logging.getLogger(__name__)

class NeedsBlockHandler(BaseBlockHandler):
    """Handler for the Needs block type"""
    
    def initialize_block(self, user_input):
        """Initialize a new Needs block"""
        return {
            "identified_as": "needs",
            "analysis": "You've identified some important needs worth addressing.",
            "suggestion": "Would you like to generate a title for these needs?"
        }


// lib/blockUtils.js

/**
 * Get welcome message based on block type
 * @param {string} blockType - Type of block
 * @returns {string} - Welcome message
 */
export const getWelcomeMessage = (blockType) => {
    const messages = {
      idea: "Welcome to the Idea Development assistant. I can help you craft innovative concepts and solutions. What would you like to explore today?",
      problem: "Welcome to the Problem Definition assistant. I can help you articulate and analyze challenges. What problem would you like to address?",
      possibility: "Welcome to the Possibility Explorer. I can help you discover potential solutions and approaches. What possibilities would you like to explore?",
      moonshot: "Welcome to Moonshot Ideation. I can help you develop ambitious, transformative ideas. What big challenge would you like to tackle?",
      needs: "Welcome to Needs Analysis. I can help you identify and understand requirements and goals. What needs would you like to analyze?",
      opportunity: "Welcome to Opportunity Assessment. I can help you discover and evaluate potential markets or directions. What opportunity interests you?",
      concept: "Welcome to Concept Development. I can help you structure and refine solutions. What concept would you like to develop?",
      outcome: "Welcome to Outcome Evaluation. I can help you measure and analyze results. What outcomes would you like to evaluate?",
      general: "Welcome to the KRAFT. I can help guide you through creative problem-solving and innovation. How can I assist you today?"
    };
    
    return messages[blockType] || "Welcome to the KRAFT. How can I assist you today?";
  };
  
  /**
   * Get information about a block type
   * @param {string} blockType - Type of block
   * @returns {Object} - Block type information
   */
  export const getBlockTypeInfo = (blockType) => {
    const blockTypes = {
      idea: {
        title: 'Idea Development',
        description: 'Craft innovative concepts',
        icon: 'fa-lightbulb'
      },
      problem: {
        title: 'Problem Definition',
        description: 'Define and explore challenges',
        icon: 'fa-question-circle'
      },
      possibility: {
        title: 'Possibility Explorer',
        description: 'Explore potential solutions',
        icon: 'fa-route'
      },
      moonshot: {
        title: 'Moonshot Ideation',
        description: 'Ideal Final Result thinking',
        icon: 'fa-rocket'
      },
      needs: {
        title: 'Needs Analysis',
        description: 'Identify requirements and goals',
        icon: 'fa-clipboard-list'
      },
      opportunity: {
        title: 'Opportunity Assessment',
        description: 'Discover potential markets',
        icon: 'fa-door-open'
      },
      concept: {
        title: 'Concept Development',
        description: 'Develop structured solutions',
        icon: 'fa-puzzle-piece'
      },
      outcome: {
        title: 'Outcome Evaluation',
        description: 'Measure and analyze results',
        icon: 'fa-flag-checkered'
      },
      general: {
        title: 'General Assistant',
        description: 'AI-powered creative guidance',
        icon: 'fa-comment'
      }
    };
    
    return blockTypes[blockType] || blockTypes.general;
  };
  
  /**
   * Map block types to their routes
   */
  export const blockTypeRoutes = {
    idea: '/blocks?type=idea',
    problem: '/blocks?type=problem',
    possibility: '/blocks?type=possibility',
    moonshot: '/blocks?type=moonshot',
    needs: '/blocks?type=needs',
    opportunity: '/blocks?type=opportunity',
    concept: '/blocks?type=concept',
    outcome: '/blocks?type=outcome',
    general: '/blocks?type=general'
  };
  
  /**
   * Get the appropriate route for a block type
   * @param {string} blockType - Type of block
   * @returns {string} - Route for the block type
   */
  export const getRouteForBlockType = (blockType) => {
    return blockTypeRoutes[blockType] || '/blocks?type=general';
  };
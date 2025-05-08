// lib/api.js
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000/api';

/**
 * API client for interacting with the backend
 */
export const api = {
  /**
   * Send a message to analyze a block
   * @param {Object} params - Parameters
   * @param {string} params.message - User message
   * @param {string} params.userId - User ID
   * @param {string} [params.blockId] - Block ID (if continuing conversation)
   * @returns {Promise<Object>} - Response data
   */
  analyzeBlock: async ({ message, userId, blockId = null }) => {
    try {
      // Determine the endpoint based on whether this is a new block or existing one
      const endpoint = blockId ? '/analysis_of_block' : '/blocks/analyze';
      
      // Prepare request body
      const requestBody = blockId 
        ? {
            message,
            user_id: userId,
            block_id: blockId
          }
        : {
            message,
            user_id: userId
          };
            
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error analyzing block:', error);
      throw error;
    }
  },
  
  /**
   * Get blocks for a user
   * @param {Object} params - Parameters
   * @param {string} params.userId - User ID
   * @param {string} [params.blockType] - Block type to filter by
   * @param {number} [params.limit] - Maximum number of blocks to return
   * @returns {Promise<Object>} - Response data with blocks
   */
  getBlocks: async ({ userId, blockType = 'all', limit = 10 }) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/blocks?user_id=${userId}&type=${blockType}&limit=${limit}`
      );
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching blocks:', error);
      throw error;
    }
  },
  
  /**
   * Get a specific block and its messages
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data with block and messages
   */
  getBlock: async ({ blockId, userId }) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/blocks/${blockId}?user_id=${userId}`
      );
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching block:', error);
      throw error;
    }
  },
  
  /**
   * Delete a block
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data
   */
  deleteBlock: async ({ blockId, userId }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/blocks/${blockId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId })
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error deleting block:', error);
      throw error;
    }
  },
  
  /**
   * Clear messages for a block
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data
   */
  clearBlock: async ({ blockId, userId }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/blocks/${blockId}/clear`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId })
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error clearing block:', error);
      throw error;
    }
  },
  
  /**
   * Create a new block
   * @param {Object} params - Parameters
   * @param {string} params.userId - User ID
   * @param {string} [params.blockType] - Block type
   * @param {string} [params.name] - Block name
   * @returns {Promise<Object>} - Response data with new block
   */
  createBlock: async ({ userId, blockType = 'general', name = null }) => {
    try {
      const defaultName = name || `New ${blockType.charAt(0).toUpperCase() + blockType.slice(1)} Block`;
      
      const response = await fetch(`${API_BASE_URL}/blocks/new`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          type: blockType,
          name: defaultName
        })
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error creating block:', error);
      throw error;
    }
  }
};

export default api;
// lib/api.js
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000/api';

/**
 * API client for interacting with the backend
 */
export const api = {
  /**
   * Fetch wrapper with error handling
   * @param {string} url - API endpoint URL
   * @param {Object} options - Fetch options
   * @returns {Promise<Object>} - Parsed response data
   */
  async fetchWithErrorHandling(url, options = {}) {
    try {
      const response = await fetch(url, options);
      
      // Handle non-2xx responses
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.error || `API error: ${response.status} ${response.statusText}`;
        throw new Error(errorMessage);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API error (${url}):`, error);
      throw error;
    }
  },

  /**
   * Send a message to analyze a block
   * @param {Object} params - Parameters
   * @param {string} params.message - User message
   * @param {string} params.userId - User ID
   * @param {string} [params.blockId] - Block ID (if continuing conversation)
   * @returns {Promise<Object>} - Response data
   */
  analyzeBlock: async ({ message, userId, blockId = null }) => {
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
          
    return api.fetchWithErrorHandling(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });
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
    return api.fetchWithErrorHandling(
      `${API_BASE_URL}/blocks?user_id=${encodeURIComponent(userId)}&type=${encodeURIComponent(blockType)}&limit=${limit}`
    );
  },
  
  /**
   * Get a specific block and its messages
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data with block and messages
   */
  getBlock: async ({ blockId, userId }) => {
    if (!blockId || !userId) {
      throw new Error('Block ID and User ID are required');
    }
    
    return api.fetchWithErrorHandling(
      `${API_BASE_URL}/blocks/${encodeURIComponent(blockId)}?user_id=${encodeURIComponent(userId)}`
    );
  },
  
  /**
   * Delete a block
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data
   */
  deleteBlock: async ({ blockId, userId }) => {
    if (!blockId || !userId) {
      throw new Error('Block ID and User ID are required');
    }
    
    return api.fetchWithErrorHandling(`${API_BASE_URL}/blocks/${encodeURIComponent(blockId)}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user_id: userId })
    });
  },
  
  /**
   * Clear messages for a block
   * @param {Object} params - Parameters
   * @param {string} params.blockId - Block ID
   * @param {string} params.userId - User ID
   * @returns {Promise<Object>} - Response data
   */
  clearBlock: async ({ blockId, userId }) => {
    if (!blockId || !userId) {
      throw new Error('Block ID and User ID are required');
    }
    
    return api.fetchWithErrorHandling(`${API_BASE_URL}/blocks/${encodeURIComponent(blockId)}/clear`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ user_id: userId })
    });
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
    if (!userId) {
      throw new Error('User ID is required');
    }
    
    const defaultName = name || `New ${blockType.charAt(0).toUpperCase() + blockType.slice(1)} Block`;
    
    return api.fetchWithErrorHandling(`${API_BASE_URL}/blocks/new`, {
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
  }
};

export default api;
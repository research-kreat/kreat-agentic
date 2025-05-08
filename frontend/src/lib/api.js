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
      const response = await fetch(`${API_BASE_URL}/analysis_of_block`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          user_id: userId,
          block_id: blockId,
        }),
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

};

export default api;
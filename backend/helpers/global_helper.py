# Helper function to sanitize response to plain text
def sanitize_response(response):
    """
    Sanitize response to ensure it's plain text without markdown or HTML
    
    Args:
        response: Response text or dict
    
    Returns:
        Sanitized response
    """
    if isinstance(response, dict):
        for key, value in response.items():
            if isinstance(value, str): 
                # Remove markdown code blocks
                value = value.replace("```", "")
                # Remove inline code
                value = value.replace("`", "")
                # Remove HTML tags (simple approach)
                value = value.replace("<", "").replace(">", "")
                response[key] = value
            elif isinstance(value, (dict, list)):
                response[key] = sanitize_response(value)
    elif isinstance(response, list):
        response = [sanitize_response(item) for item in response]
    elif isinstance(response, str):
        # Remove markdown code blocks
        response = response.replace("```", "")
        # Remove inline code
        response = response.replace("`", "")
        # Remove HTML tags (simple approach)
        response = response.replace("<", "").replace(">", "")
    
    return response

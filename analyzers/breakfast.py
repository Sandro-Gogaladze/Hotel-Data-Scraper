"""
Functionality for analyzing breakfast descriptions using GPT-4.

This module leverages the OpenAI API (GPT-4) to determine whether the breakfast
description provided implies that breakfast is included for free or if there is an extra cost.
"""

import os
import sys
import openai
from typing import Any

# Ensure correct module path resolution, regardless of where the script is run from.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from config import OPENAI_API_KEY, GPT_MODEL, GPT_TEMPERATURE, GPT_MAX_TOKENS

# Set the OpenAI API key from configuration.
openai.api_key = OPENAI_API_KEY

def analyze_breakfast_with_gpt4(breakfast_text: str) -> bool:
    """
    Uses GPT-4 to determine if breakfast is included for free based on a provided description.
    
    The function sends a prompt to the GPT model asking it to decide if the breakfast
    text implies that breakfast is free. If any cost is mentioned, it expects a "false" result.
    Only "true" or "false" should be returned by the model.
    
    Args:
        breakfast_text: A string containing the breakfast options description.
        
    Returns:
        True if GPT-4 indicates that breakfast is free, False otherwise.
    """
    log_message(f"Analyzing breakfast text: {breakfast_text}", "debug")
    
    try:
        # Prepare a prompt to instruct GPT-4 how to analyze the breakfast description.
        prompt = f"""
Analyze the following hotel breakfast description and determine whether breakfast is included for free. 
If the description mentions a price or cost for breakfast, then answer "false". 
Only answer with "true" or "false".

Breakfast description:
"{breakfast_text}"

Examples:
- "Very good breakfast included" → true
- "Exceptional breakfast GEL 35" → false
- "Continental breakfast included" → true
- "Full English breakfast (€15)" → false

Respond with only "true" or "false".
"""
        # Call the OpenAI ChatCompletion API using provided GPT parameters.
        response: Any = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=GPT_TEMPERATURE,
            max_tokens=GPT_MAX_TOKENS
        )
        # Extract and normalize the GPT response.
        result: str = response.choices[0].message.content.strip().lower()
        is_free: bool = (result == "true")
        log_message(f"Breakfast analysis result: {is_free} (GPT response: {result})", "debug")
        return is_free
    except Exception as e:
        # Log any exception that occurs during the API call and return False.
        log_message(f"Error calling GPT-4 API: {e}", "error")
        return False

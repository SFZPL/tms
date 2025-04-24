import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import openai  # Import the entire openai module instead of OpenAI class
from config import get_secret

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='azure_llm.log'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Replace current initialization
try:
    from openai import OpenAI
    client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))
    DEFAULT_MODEL = get_secret("OPENAI_MODEL", "gpt-4o")
    logger.info(f"OpenAI initialized with default model: {DEFAULT_MODEL}")
except Exception as e:
    logger.error(f"Error initializing OpenAI: {e}", exc_info=True)
    client = None
def analyze_email(email_text: str, model: str = None) -> dict:
    """
    Extracts relevant service request details from an email using OpenAI.
    
    Args:
        email_text: The email text to analyze
        model: Optional OpenAI model to use (defaults to environment variable or gpt-4)
        
    Returns:
        Dictionary with extracted information
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return {"error": "OpenAI API key not set. Check API key and configuration."}
    
    if not email_text:
        logger.warning("Empty email text provided")
        return {"error": "No email text provided for analysis."}
    
    # Use specified model or default
    model_to_use = model or DEFAULT_MODEL
    
    logger.info(f"Analyzing email with model: {model_to_use}")
    
    try:
        # System prompt to guide the model
        system_prompt = """You are an expert in extracting structured information from client emails for a task management system.
Extract all relevant details for a service request including:
- Client/customer name
- Project name/reference
- Sales order number or reference (if present)
- Requested services
- Timeline/deadlines
- Special requirements
- Service categories (if mentioned)
- Design units (if mentioned)
- Target language (if mentioned)

Format your response as a JSON object with these fields:
client, project, order_reference, services, deadline, requirements, service_category_1, service_category_2, design_units, target_language.

If you can't find information for a field, leave it as an empty string."""
        
        # Make API call with older openai library syntax
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract all relevant details for a service request from the email below:\n\n{email_text}"}
            ],
            max_tokens=800,
            temperature=0.3,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
        )
        
        # Extract the content
        extracted_info = response.choices[0].message.content.strip()
        logger.info("Email analysis completed successfully")
        
        # Try to parse the JSON response
        import json
        try:
            extracted_dict = json.loads(extracted_info)
            return extracted_dict
        except json.JSONDecodeError:
            # If parsing as JSON fails, return the raw text
            logger.warning("Failed to parse email analysis as JSON")
            return {"raw_analysis": extracted_info}
        
    except Exception as e:
        logger.error(f"Error analyzing email: {e}", exc_info=True)
        return {"error": f"Error analyzing email: {str(e)}"}

def suggest_task_categories(task_description: str, model: str = None) -> Dict[str, Any]:
    """
    Suggests appropriate service categories based on task description.
    
    Args:
        task_description: Description of the task
        model: Optional OpenAI model to use
        
    Returns:
        Dictionary with suggested categories and confidence scores
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return {"error": "OpenAI API key not set. Check API key and configuration."}
    
    if not task_description:
        logger.warning("Empty task description provided")
        return {"error": "No task description provided."}
    
    # Use specified model or default
    model_to_use = model or DEFAULT_MODEL
    
    logger.info(f"Suggesting task categories with model: {model_to_use}")
    
    try:
        # System prompt to guide the model
        system_prompt = """You are an expert in task categorization for a traffic management system.
Based on the task description, suggest the most appropriate primary and secondary service categories.
Return your response in JSON format with the following structure:
{
  "primary_category": "Category name",
  "primary_confidence": 0.95,
  "secondary_category": "Category name",
  "secondary_confidence": 0.85,
  "design_units_estimate": 5
}"""
        
        # Make API call with older openai library syntax
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Suggest appropriate service categories for this task:\n\n{task_description}"}
            ],
            max_tokens=500,
            temperature=0.3,
        )
        
        # Parse response as JSON
        import json
        result = json.loads(response.choices[0].message.content.strip())
        logger.info("Category suggestion completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error suggesting categories: {e}", exc_info=True)
        return {"error": str(e)}

# Additional utility function
def estimate_task_duration(task_description: str, model: str = None) -> Dict[str, Any]:
    """
    Estimates the time required to complete a task based on its description.
    
    Args:
        task_description: Description of the task
        model: Optional OpenAI model to use
        
    Returns:
        Dictionary with estimated hours and confidence level
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return {"error": "OpenAI API key not set. Check API key and configuration."}
    
    if not task_description:
        logger.warning("Empty task description provided")
        return {"error": "No task description provided."}
    
    # Use specified model or default
    model_to_use = model or DEFAULT_MODEL
    
    logger.info(f"Estimating task duration with model: {model_to_use}")
    
    try:
        # System prompt to guide the model
        system_prompt = """You are an expert in estimating the time required for traffic management tasks.
Based on the task description, estimate the hours required to complete the task.
Return your response in JSON format with the following structure:
{
  "estimated_hours": 4.5,
  "confidence": "high|medium|low",
  "reasoning": "Brief explanation of your estimate"
}"""
        
        # Make API call with older openai library syntax
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Estimate the time required for this task:\n\n{task_description}"}
            ],
            max_tokens=500,
            temperature=0.3,
        )
        
        # Parse response as JSON
        import json
        result = json.loads(response.choices[0].message.content.strip())
        logger.info("Duration estimation completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error estimating task duration: {e}", exc_info=True)
        return {"error": str(e)}
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
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
    global client
    """
    Enhanced email analysis that extracts comprehensive service request details.
    
    Args:
        email_text: The email text to analyze
        model: Optional OpenAI model to use (defaults to environment variable or gpt-4)
        
    Returns:
        Dictionary with extracted information including suggested task names
    """
    if not client:
        logger.error("OpenAI client not initialized")
        return {"error": "OpenAI client not initialized. Check API key and configuration."}
    
    if not email_text:
        logger.warning("Empty email text provided")
        return {"error": "No email text provided for analysis."}
    
    # Use specified model or default
    model_to_use = model or DEFAULT_MODEL
    
    logger.info(f"Analyzing email with model: {model_to_use}")
    
    try:
        # Enhanced system prompt for comprehensive analysis
        system_prompt = """You are an expert in extracting structured information from client emails for a task management system.
Your goal is to analyze the email and extract ALL relevant details that can be used to automatically fill in task creation forms.

Extract the following information:
1. Client/customer name and company
2. Project name/reference
3. Sales order number or reference (if present)
4. Requested services (be specific)
5. Timeline/deadlines (both client requested and suggested internal deadlines)
6. Special requirements or instructions
7. Service categories (classify the work type)
8. Design units estimation (if applicable)
9. Target language (if mentioned)
10. Suggested parent task title (create a descriptive title based on the main request)
11. Suggested subtask titles (break down the work into logical subtasks)
12. Urgency level (high/medium/low based on language and deadlines)
13. Any attachments or references mentioned
14. Contact person details

Format your response as a JSON object with these fields:
{
    "client": "client name",
    "company": "company name",
    "project": "project name",
    "order_reference": "SO number or reference",
    "services": "detailed list of requested services",
    "client_deadline": "client's requested deadline",
    "suggested_internal_deadline": "suggested internal deadline (2-3 days before client deadline)",
    "requirements": "special requirements or instructions",
    "service_category_1": "primary service category",
    "service_category_2": "secondary service category if applicable",
    "design_units": "estimated design units if applicable",
    "target_language": "target language if mentioned",
    "parent_task_title": "suggested descriptive parent task title",
    "subtask_suggestions": ["subtask 1 title", "subtask 2 title", ...],
    "urgency": "high/medium/low",
    "attachments_mentioned": "any files or references mentioned",
    "contact_person": "name and contact details",
    "additional_notes": "any other relevant information"
}

Be creative with task titles - make them descriptive and action-oriented. For subtasks, break down the work logically based on the services requested.
If you can't find information for a field, use an empty string, but try to infer reasonable values where possible."""
        
        # Make API call
        response = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract all relevant details for task creation from this email:\n\n{email_text}"}
            ],
            max_tokens=1200,
            temperature=0.3,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
        )
        
        # Extract the content
        extracted_info = response.choices[0].message.content.strip()
        logger.info("Enhanced email analysis completed successfully")
        
        # Try to parse the JSON response
        import json
        try:
            extracted_dict = json.loads(extracted_info)
            
            # Post-process the data to ensure quality
            # Ensure subtask_suggestions is a list
            if isinstance(extracted_dict.get("subtask_suggestions"), str):
                extracted_dict["subtask_suggestions"] = [extracted_dict["subtask_suggestions"]]
            
            # Generate parent task title if not provided
            if not extracted_dict.get("parent_task_title"):
                services = extracted_dict.get("services", "")
                client = extracted_dict.get("client", "")
                if services and client:
                    extracted_dict["parent_task_title"] = f"{services} for {client}"
                elif services:
                    extracted_dict["parent_task_title"] = services
                else:
                    extracted_dict["parent_task_title"] = "New Service Request"
            
            # Generate subtask suggestions if not provided
            if not extracted_dict.get("subtask_suggestions") or len(extracted_dict["subtask_suggestions"]) == 0:
                services = extracted_dict.get("services", "")
                if services:
                    # Create basic subtasks based on common workflow
                    extracted_dict["subtask_suggestions"] = [
                        f"Initial Review and Planning - {services}",
                        f"Design/Development - {services}",
                        f"Internal Review and Quality Check",
                        f"Client Review and Revisions",
                        f"Final Delivery"
                    ]
            
            # Set suggested internal deadline if not provided
            if extracted_dict.get("client_deadline") and not extracted_dict.get("suggested_internal_deadline"):
                try:
                    from datetime import datetime, timedelta
                    import re
                    
                    # Try to parse the deadline
                    deadline_text = extracted_dict["client_deadline"]
                    # This is simplified - in production you'd want more robust date parsing
                    if "tomorrow" in deadline_text.lower():
                        internal = "Today EOD"
                    elif "urgent" in deadline_text.lower() or "asap" in deadline_text.lower():
                        internal = "Within 24 hours"
                    elif "days" in deadline_text.lower():
                        # Extract number of days and subtract 2
                        match = re.search(r'(\d+)\s*days?', deadline_text.lower())
                        if match:
                            days = int(match.group(1))
                            internal_days = max(1, days - 2)
                            internal = f"Within {internal_days} days"
                        else:
                            internal = "2 days before client deadline"
                    else:
                        internal = "2 days before client deadline"
                    
                    extracted_dict["suggested_internal_deadline"] = internal
                except:
                    extracted_dict["suggested_internal_deadline"] = "2 days before client deadline"
            
            return extracted_dict
        except json.JSONDecodeError:
            # If parsing as JSON fails, return the raw text
            logger.warning("Failed to parse enhanced email analysis as JSON")
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
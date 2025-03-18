import os
import logging
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
from dotenv import load_dotenv
import openai  # Import the entire openai module instead of OpenAI class
from config import get_secret
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='designer_selector.log'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define data path
DATA_DIR = Path(get_secret("DATA_DIR", "."))
DEFAULT_DESIGNER_FILE = get_secret("DESIGNER_FILE", "Cleaned_Assignment_Guide.xlsx")

# Initialize OpenAI with API key from config
try:
    openai.api_key = get_secret("OPENAI_API_KEY")
    # Default model if not specified in environment variables
    DEFAULT_MODEL = get_secret("OPENAI_MODEL", "gpt-3.5-turbo")
    logger.info(f"OpenAI initialized with default model: {DEFAULT_MODEL}")
except Exception as e:
    logger.error(f"Error initializing OpenAI: {e}", exc_info=True)
    openai.api_key = None

def safe_api_call(func, *args, retries=3, delay=7, **kwargs):
    """
    Wrapper for API calls that retries if an error occurs.
    
    Args:
        func: Function to call
        retries: Number of retries
        delay: Delay between retries in seconds
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Result of the function call
    """
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"API call failed (attempt {i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                logger.error(f"API call failed after {retries} attempts: {e}", exc_info=True)
                raise

def load_designers(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Loads designer information from an Excel file.
    
    Args:
        file_path: Path to the Excel file (optional)
        
    Returns:
        DataFrame containing designer information
    """
    try:
        # Use provided path, or find the file in the data directory
        if file_path:
            path = Path(file_path)
        else:
            # Look for the file in the data directory
            path = DATA_DIR / DEFAULT_DESIGNER_FILE
            
            # If not found, check current directory
            if not path.exists():
                path = Path(DEFAULT_DESIGNER_FILE)
        
        if not path.exists():
            logger.error(f"Designer file not found: {path}")
            raise FileNotFoundError(f"Designer file not found: {path}")
        
        logger.info(f"Loading designers from: {path}")
        designers_df = pd.read_excel(path)
        
        # Basic data cleaning
        designers_df = designers_df.fillna('')
        
        # Convert all string columns to strings (in case they're mixed types)
        for col in designers_df.columns:
            if designers_df[col].dtype == object:
                designers_df[col] = designers_df[col].astype(str)
                
        logger.info(f"Loaded {len(designers_df)} designers")
        return designers_df
        
    except Exception as e:
        logger.error(f"Error loading designers: {e}", exc_info=True)
        # Return empty DataFrame instead of raising exception
        return pd.DataFrame(columns=['Name', 'Position', 'Tools', 'Outputs', 'Languages'])

def prepare_compact_designer_summary(designers_df: pd.DataFrame, max_designers: int = 5) -> str:
    """
    Converts the top max_designers rows of the designers DataFrame into a compact summary.
    
    Args:
        designers_df: DataFrame containing designer information
        max_designers: Maximum number of designers to include
        
    Returns:
        String with one designer per line in a compact format
    """
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return "No designers available"
    
    try:
        selected_designers = designers_df.head(max_designers)
        summaries = []
        
        for _, row in selected_designers.iterrows():
            # Using a pipe delimiter for compactness
            line = (
                f"{row.get('Name', 'N/A')}|"
                f"{row.get('Position', 'N/A')}|"
                f"{row.get('Tools', 'N/A')}|"
                f"{row.get('Outputs', 'N/A')}|"
                f"{row.get('Languages', 'N/A')}"
            )
            summaries.append(line)
            
        logger.info(f"Prepared summary for {len(summaries)} designers")
        return "\n".join(summaries)
        
    except Exception as e:
        logger.error(f"Error preparing designer summary: {e}", exc_info=True)
        return "Error preparing designer summary"

def suggest_best_designer(request_info: str, designers_df: pd.DataFrame, max_designers: int = 5) -> str:
    """
    Suggests the best designer for a service request.
    
    Args:
        request_info: Details of the service request
        designers_df: DataFrame containing designer information
        max_designers: Maximum number of designers to consider
        
    Returns:
        String with the best designer suggestion
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return "Error: OpenAI API not available. Please check your configuration."
    
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return "No designers available to match with your request."
    
    try:
        # Prepare designer summary
        designers_summary = prepare_compact_designer_summary(designers_df, max_designers=max_designers)
        
        # Prepare prompt
        system_prompt = """You are a seasoned design consultant specializing in matching project requirements to designer capabilities.
Your task is to analyze the service request details and recommend the best designer from the provided profiles.
Return your recommendation in the format: "Designer Name: <n>. Explanation: <brief explanation>."
Be concise but include key reasons for your selection."""
        
        user_prompt = f"""Based on the following service request details and the available designer profiles, 
recommend the single best designer:

Service Request Details:
{request_info}

Designer Profiles (each line is: Name|Position|Tools|Outputs|Languages):
{designers_summary}"""
        
        # Make API call using older openai library syntax
        response = safe_api_call(
            openai.ChatCompletion.create,
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250,
            temperature=0.3,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
        )
        
        # Extract suggestion
        suggestion = response.choices[0].message.content.strip()
        logger.info(f"Designer suggestion: {suggestion[:50]}...")
        return suggestion
        
    except Exception as e:
        logger.error(f"Error suggesting designer: {e}", exc_info=True)
        return f"Error suggesting designer: {str(e)}"

def filter_designers_by_availability(designers_df: pd.DataFrame, models, uid, deadline, task_duration) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filters designers based on availability before the deadline.
    
    Args:
        designers_df: DataFrame containing designer information
        models: Odoo models proxy
        uid: User ID
        deadline: Deadline by which the task must be completed
        task_duration: Duration of the task in hours
        
    Returns:
        Tuple of DataFrames (available, not_available)
    """
    from helpers import get_all_employees_in_planning, get_employee_schedule, find_employee_id, find_earliest_available_slot
    
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return pd.DataFrame(), pd.DataFrame()
    
    try:
        logger.info(f"Checking availability for {len(designers_df)} designers")
        
        # Get all employees from planning
        employees = get_all_employees_in_planning(models, uid)
        available = []
        not_available = []
        
        for _, row in designers_df.iterrows():
            name = row.get("Name", "")
            
            # Find employee ID
            employee_id = find_employee_id(name, employees)
            
            if not employee_id:
                logger.warning(f"Employee not found in planning: {name}")
                not_available.append(row)
                continue
                
            # Get employee schedule
            schedule = get_employee_schedule(models, uid, employee_id)
            
            # Find available slot
            slot = find_earliest_available_slot(schedule, task_duration, deadline)
            
            if slot[0] is not None:
                logger.info(f"Designer available: {name}")
                row_copy = row.copy()
                # Add availability information to the row
                row_copy['available_from'] = slot[0]
                row_copy['available_until'] = slot[1]
                available.append(row_copy)
            else:
                logger.info(f"Designer not available: {name}")
                not_available.append(row)
        
        # Convert to DataFrames
        available_df = pd.DataFrame(available) if available else pd.DataFrame()
        not_available_df = pd.DataFrame(not_available) if not_available else pd.DataFrame()
        
        logger.info(f"Found {len(available_df)} available designers and {len(not_available_df)} unavailable designers")
        return available_df, not_available_df
        
    except Exception as e:
        logger.error(f"Error filtering designers by availability: {e}", exc_info=True)
        # Return empty DataFrames on error
        return pd.DataFrame(), pd.DataFrame()

def suggest_best_designer_available(request_info: str, available_designers_df: pd.DataFrame, 
                                   not_available_designers_df: pd.DataFrame, max_designers: int = 5) -> str:
    """
    Suggests the best available designer for a service request.
    
    Args:
        request_info: Details of the service request
        available_designers_df: DataFrame containing available designer information
        not_available_designers_df: DataFrame containing unavailable designer information
        max_designers: Maximum number of designers to consider
        
    Returns:
        String with the best designer suggestion
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return "Error: OpenAI API not available. Please check your configuration."
    
    if available_designers_df.empty and not_available_designers_df.empty:
        logger.warning("Empty designers DataFrames provided")
        return "No designers available to match with your request."
    
    try:
        # Prepare designer summaries
        available_summary = prepare_compact_designer_summary(available_designers_df, max_designers=max_designers)
        not_available_summary = prepare_compact_designer_summary(not_available_designers_df, max_designers=max_designers)
        
        # Prepare prompt
        system_prompt = """You are a seasoned design consultant specializing in matching project requirements to designer capabilities and availability.
Your task is to analyze the service request details and recommend the best designer from the available profiles.
Return your recommendation in the format: "Designer Name: <n>. Explanation: <brief explanation>."
At the end, note which designers would be good matches but are not currently available."""
        
        user_prompt = f"""Based on the following service request details and the available designer profiles, 
recommend the single best designer that is available to complete the task:

Service Request Details:
{request_info}

Available Designer Profiles (each line: Name|Position|Tools|Outputs|Languages):
{available_summary}

Not Available Designer Profiles (each line: Name|Position|Tools|Outputs|Languages):
{not_available_summary}"""
        
        # Make API call using older openai library syntax
        response = safe_api_call(
            openai.ChatCompletion.create,
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=350,
            temperature=0.3,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
        )
        
        # Extract suggestion
        suggestion = response.choices[0].message.content.strip()
        logger.info(f"Designer availability suggestion: {suggestion[:50]}...")
        return suggestion
        
    except Exception as e:
        logger.error(f"Error suggesting available designer: {e}", exc_info=True)
        return f"Error suggesting available designer: {str(e)}"

# Additional utility function
def rank_designers_by_skill_match(request_info: str, designers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ranks all designers based on their skill match to the request.
    
    Args:
        request_info: Details of the service request
        designers_df: DataFrame containing designer information
        
    Returns:
        DataFrame with designers ranked by match score
    """
    if not openai.api_key:
        logger.error("OpenAI API key not set")
        return designers_df.assign(match_score=0.0, match_reason="API not available")
    
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return designers_df
    
    try:
        # Prepare designer summary (include all designers)
        designers_summary = prepare_compact_designer_summary(designers_df, max_designers=len(designers_df))
        
        # Prepare prompt
        system_prompt = """You are a design team coordinator who needs to rank designers based on their skills.
Analyze the service request details and rank each designer with a score from 0 to 100.
Return your analysis in JSON format with an array of objects, each containing:
{
  "name": "Designer Name",
  "score": 85,
  "reason": "Brief explanation of score"
}
Include ALL designers from the provided list."""
        
        user_prompt = f"""Based on the following service request details and the available designer profiles, 
rank each designer on their match to the requirements:

Service Request Details:
{request_info}

Designer Profiles (each line is: Name|Position|Tools|Outputs|Languages):
{designers_summary}"""
        
        # Make API call using older openai library syntax
        response = safe_api_call(
            openai.ChatCompletion.create,
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500,
            temperature=0.3,
        )
        
        # Parse JSON response
        import json
        result = json.loads(response.choices[0].message.content.strip())
        
        # Create a dictionary to map designer names to scores and reasons
        designer_scores = {}
        for item in result.get("designers", []):
            designer_scores[item.get("name", "")] = {
                "score": item.get("score", 0),
                "reason": item.get("reason", "")
            }
        
        # Add scores to the DataFrame
        designers_df = designers_df.copy()
        designers_df["match_score"] = designers_df["Name"].apply(
            lambda x: designer_scores.get(x, {}).get("score", 0) if x in designer_scores else 0
        )
        designers_df["match_reason"] = designers_df["Name"].apply(
            lambda x: designer_scores.get(x, {}).get("reason", "") if x in designer_scores else ""
        )
        
        # Sort by match score
        ranked_df = designers_df.sort_values("match_score", ascending=False).reset_index(drop=True)
        
        logger.info(f"Ranked {len(ranked_df)} designers by skill match")
        return ranked_df
        
    except Exception as e:
        logger.error(f"Error ranking designers: {e}", exc_info=True)
        # Return original DataFrame with empty scores on error
        return designers_df.assign(match_score=0.0, match_reason=f"Error: {str(e)}")
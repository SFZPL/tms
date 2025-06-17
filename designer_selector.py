import os
import logging
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
from dotenv import load_dotenv
import streamlit as st
from openai import OpenAI  # Import the OpenAI class for v1.0+
from config import get_secret  # Move this AFTER streamlit import

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

# Add this after imports but before client initialization
import inspect

# Then update the client initialization try/except with more debugging:
try:
    api_key = get_secret("OPENAI_API_KEY")
    logger.info(f"Initializing OpenAI with key (first 8 chars): {api_key[:8] if api_key else 'None'}...")
    
    if api_key:
        client = OpenAI(api_key=api_key)
        logger.info("Successfully created OpenAI client with v1.35.3")
        
        # Test the client with a simple API call
        try:
            models = client.models.list()
            logger.info(f"API test successful! Available models: {len(list(models.data))}")
        except Exception as test_err:
            logger.error(f"API test failed: {test_err}")
    else:
        logger.error("No OpenAI API key found")
        client = None
        
    DEFAULT_MODEL = get_secret("OPENAI_MODEL", "gpt-4")
    logger.info(f"Default model set to: {DEFAULT_MODEL}")
except Exception as e:
    logger.error(f"OpenAI initialization failed: {e}", exc_info=True)
    client = None

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

    # Debug check
    if not client:
        logger.error("OpenAI client is None!")
        return "Error: OpenAI API not available. Please check your configuration."
    
    # Add more debug info
    if hasattr(client, 'api_key') and client.api_key:
        logger.info(f"Client has API key (starts with): {client.api_key[:8]}...")
    else:
        logger.info("Client doesn't have direct api_key attribute")

    
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return "No designers available to match with your request."
    
    try:
        # Prepare designer summary
        designers_summary = prepare_compact_designer_summary(designers_df, max_designers=max_designers)
        
        # Prepare prompt
        system_prompt = """You are a design team coordinator who needs to rank designers based on their skills.
        Analyze the service request details and rank each designer with a meaningful score from 0 to 100.
        AVOID giving everyone the same score. Differentiate between designers based on their skills.

        Return your analysis in this EXACT JSON format:
        {
        "designers": [
            {
            "name": "Designer Name",
            "score": 85,
            "reason": "Brief explanation of score"
            },
            {
            "name": "Another Designer",
            "score": 72,
            "reason": "Different explanation"
            }
        ]
        }

        IMPORTANT: Include ALL designers from the provided list and give reasonable scores that reflect skill match.
        DO NOT give everyone a 0% match - use the full 0-100 range with proper differentiation."""
        
        user_prompt = f"""Based on the following service request details and the available designer profiles, 
recommend the single best designer:

Service Request Details:
{request_info}

Designer Profiles (each line is: Name|Position|Tools|Outputs|Languages):
{designers_summary}"""
        
        # Make API call using older openai library syntax
        response = safe_api_call(
            client.chat.completions.create,
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
        suggestion = response.choices[0].message.content
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
                # Get information about why they're unavailable
                row_copy = row.copy()
                
                # Find the task that's blocking them
                blocking_task = None
                for task in schedule:
                    task_start = pd.to_datetime(task['start_datetime'])
                    task_end = pd.to_datetime(task['end_datetime'])
                    if task_start <= deadline and task_end >= deadline:
                        blocking_task = task
                        break
                
                if blocking_task:
                    # Get task details from Odoo
                    task_id = blocking_task.get('task_id')
                    if task_id:
                        task_details = models.execute_kw(
                            st.session_state.odoo_credentials['db'], uid, st.session_state.odoo_credentials['password'],
                            'project.task', 'read',
                            [[task_id]],
                            {'fields': ['name', 'x_studio_client_due_date_3', 'date_deadline']}
                        )
                        if task_details:
                            task_details = task_details[0]
                            row_copy['blocking_task_name'] = task_details.get('name', 'Unknown Task')
                            # Try to get client due date first, fall back to internal deadline, then slot end_datetime
                            row_copy['blocking_task_deadline'] = (
                                task_details.get('x_studio_client_due_date_3') or 
                                task_details.get('date_deadline') or 
                                blocking_task.get('end_datetime')
                            )
                        else:
                            row_copy['blocking_task_name'] = 'Unknown Task'
                            row_copy['blocking_task_deadline'] = blocking_task.get('end_datetime')
                    else:
                        row_copy['blocking_task_name'] = 'Unknown Task'
                        row_copy['blocking_task_deadline'] = blocking_task.get('end_datetime')
                else:
                    row_copy['blocking_task_name'] = 'Unknown Task'
                    row_copy['blocking_task_deadline'] = None
                
                not_available.append(row_copy)
        
        # Ensure all unavailable designers have the required keys
        for row in not_available:
            if 'blocking_task_deadline' not in row:
                row['blocking_task_deadline'] = None
            if 'blocking_task_name' not in row:
                row['blocking_task_name'] = 'Unknown Task'
        
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
            client.chat.completions.create,
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
    
    if designers_df.empty:
        logger.warning("Empty designers DataFrame provided")
        return designers_df
    
    try:
        # Prepare designer summary (include all designers)
        designers_summary = prepare_compact_designer_summary(designers_df, max_designers=len(designers_df))
        
        # Prepare prompt
        # Replace the system_prompt in rank_designers_by_skill_match with:
        system_prompt = """You are a design team coordinator who needs to rank designers based on their skills.
        Analyze the service request details and rank each designer with a meaningful score from 0 to 100.
        AVOID giving everyone the same score. Differentiate between designers based on their skills.

        Return your analysis in this EXACT JSON format:
        {
        "designers": [
            {
            "name": "Designer Name",
            "score": 85,
            "reason": "Brief explanation of score"
            },
            {
            "name": "Another Designer",
            "score": 72,
            "reason": "Different explanation"
            }
        ]
        }

        IMPORTANT: Include ALL designers from the provided list and give reasonable scores that reflect skill match.
        DO NOT give everyone a 0% match - use the full 0-100 range with proper differentiation."""
        
        user_prompt = f"""Based on the following service request details and the available designer profiles, 
rank each designer on their match to the requirements:

Service Request Details:
{request_info}

Designer Profiles (each line is: Name|Position|Tools|Outputs|Languages):
{designers_summary}"""
        
        # Make API call using older openai library syntax
        response = safe_api_call(
            client.chat.completions.create,
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500,
            temperature=0.3,
        )
        
        # Parse JSON response
        # Parse JSON response
        import json
        try:
            # Log the raw response for debugging
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Raw AI response: {response_text[:200]}...")  # Log first 200 chars
            
            # Try to parse the JSON
            result = json.loads(response_text)
            
            # Check for different possible JSON structures
            designer_scores = {}
            
            # Case 1: Array of designers directly in result
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and "name" in item:
                        designer_scores[item.get("name", "")] = {
                            "score": item.get("score", 50),  # Default to 50% if no score
                            "reason": item.get("reason", "")
                        }
            
            # Case 2: Designers in a "designers" key
            elif isinstance(result, dict) and "designers" in result and isinstance(result["designers"], list):
                for item in result["designers"]:
                    if isinstance(item, dict) and "name" in item:
                        designer_scores[item.get("name", "")] = {
                            "score": item.get("score", 50),  # Default to 50% if no score
                            "reason": item.get("reason", "")
                        }
            
            # Case 3: Direct mapping of names to scores
            elif isinstance(result, dict):
                for name, data in result.items():
                    if isinstance(data, dict) and "score" in data:
                        designer_scores[name] = {
                            "score": data.get("score", 50),
                            "reason": data.get("reason", "")
                        }
                    elif isinstance(data, (int, float)):
                        designer_scores[name] = {
                            "score": data,
                            "reason": ""
                        }
            
            # If we still have no scores but have designers, create default scores
            if not designer_scores and not designers_df.empty:
                for _, row in designers_df.iterrows():
                    name = row.get("Name", "")
                    if name:
                        designer_scores[name] = {
                            "score": 50,  # Default 50% match
                            "reason": "Default score assigned"
                        }
            
            logger.info(f"Extracted scores for {len(designer_scores)} designers")
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            # Create default scores on error
            designer_scores = {}
            for _, row in designers_df.iterrows():
                name = row.get("Name", "")
                if name:
                    designer_scores[name] = {
                        "score": 30 + hash(name) % 40,  # Random-ish scores between 30-70%
                        "reason": "Score estimated due to processing error"
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

def suggest_reshuffling(available_designers: pd.DataFrame, unavailable_designers: pd.DataFrame, 
                       current_task_deadline: datetime, current_task_duration: int) -> Optional[Dict]:
    """
    Suggests task reshuffling if an unavailable designer is a better match.
    
    Args:
        available_designers: DataFrame of available designers
        unavailable_designers: DataFrame of unavailable designers
        current_task_deadline: Deadline of the current task
        current_task_duration: Duration of the current task in hours
        
    Returns:
        Dictionary with reshuffling suggestion if applicable, None otherwise
    """
    if unavailable_designers.empty or available_designers.empty:
        return None
    
    # Debug printout: show top unavailable designers, their scores, and blocking deadlines
    debug_rows = unavailable_designers.head(5)
    logger.info("Top unavailable designers for reshuffling consideration:")
    for idx, row in debug_rows.iterrows():
        logger.info(f"  Name: {row.get('Name')}, Match Score: {row.get('match_score')}, Blocking Task Deadline: {row.get('blocking_task_deadline')}")
    
    # Find the best available designer's match score
    best_available_score = available_designers['match_score'].max() if 'match_score' in available_designers else 0
    
    # Find unavailable designers with better match scores
    better_unavailable = unavailable_designers[
        (unavailable_designers['match_score'] > best_available_score) & 
        (unavailable_designers['blocking_task_deadline'] > current_task_deadline.strftime('%Y-%m-%d'))
    ]
    
    if better_unavailable.empty:
        return None
    
    # Get the best unavailable designer
    best_unavailable = better_unavailable.iloc[0]
    
    return {
        'designer_name': best_unavailable['Name'],
        'match_score': best_unavailable['match_score'],
        'blocking_task_name': best_unavailable.get('blocking_task_name', 'Unknown Task'),
        'blocking_task_deadline': best_unavailable.get('blocking_task_deadline'),
        'current_task_deadline': current_task_deadline.strftime('%Y-%m-%d'),
        'current_task_duration': current_task_duration,
        'best_available_score': best_available_score
    }
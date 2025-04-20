import streamlit as st
import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from google.oauth2.credentials import Credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='config.log'
)
logger = logging.getLogger(__name__)

def get_secret(key: str, default: Any = None) -> Any:
    """
    Get a secret from Streamlit secrets or environment variables.
    
    Args:
        key: The key to look for
        default: Default value if not found
        
    Returns:
        The secret value or default
    """
    # Try to get from st.secrets first
    parts = key.split('.')
    
    # Handle nested secret keys like 'google.drive_parent_folder_id'
    if len(parts) > 1:
        current = st.secrets
        for part in parts:
            if part in current:
                current = current[part]
            else:
                current = None
                break
        if current is not None:
            return current
    # Handle flat keys
    elif key in st.secrets:
        return st.secrets[key]
        
    # Fall back to environment variables
    return os.getenv(key, default)

def get_google_credentials():
    """Get Google API credentials as a dictionary."""
    try:
        # Get client config from Streamlit secrets
        client_config_str = st.secrets.get("gcp", {}).get("client_config")
        if client_config_str:
            return json.loads(client_config_str)
        return None
    except Exception as e:
        logger.error(f"Error parsing Google credentials: {e}")
        return None

def get_user_creds_path(username):
    """
    Get path to user credentials file
    
    Args:
        username: Username to get credentials for
        
    Returns:
        Path object for the credentials file
    """
    creds_dir = Path("user_credentials")
    creds_dir.mkdir(exist_ok=True)
    return creds_dir / f"{username}_google_creds.json"

def save_user_google_creds(username, creds_dict):
    """
    Save Google credentials for specific user
    
    Args:
        username: Username to save credentials for
        creds_dict: Dictionary containing credential objects
        
    Returns:
        True if successful, False otherwise
    """
    if not username or username == "Not logged in":
        return False
        
    try:
        # We need to convert credentials object to serializable format
        creds = creds_dict.get("gmail_creds")
        if not creds:
            logger.warning(f"No credentials to save for user {username}")
            return False
            
        serializable_creds = {
            "token": creds.token if hasattr(creds, 'token') else None,
            "refresh_token": creds.refresh_token if hasattr(creds, 'refresh_token') else None,
            "token_uri": creds.token_uri if hasattr(creds, 'token_uri') else None,
            "client_id": creds.client_id if hasattr(creds, 'client_id') else None,
            "client_secret": creds.client_secret if hasattr(creds, 'client_secret') else None,
            "scopes": creds.scopes if hasattr(creds, 'scopes') else None,
            "google_auth_complete": creds_dict.get("google_auth_complete", False)
        }
        
        creds_path = get_user_creds_path(username)
        with open(creds_path, "w") as f:
            json.dump(serializable_creds, f)
        logger.info(f"Saved Google credentials for user {username}")
        return True
    except Exception as e:
        logger.error(f"Error saving Google credentials: {e}")
        return False

def load_user_google_creds(username):
    """
    Load Google credentials for specific user
    
    Args:
        username: Username to load credentials for
        
    Returns:
        Dictionary with credential objects or None if not found
    """
    if not username or username == "Not logged in":
        return None
        
    creds_path = get_user_creds_path(username)
    if not creds_path.exists():
        logger.info(f"No saved credentials found for user {username}")
        return None
        
    try:
        with open(creds_path, "r") as f:
            creds_data = json.load(f)
            
        # Convert serialized data back to credentials object
        if creds_data.get("token"):
            creds = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri"),
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret"),
                scopes=creds_data.get("scopes")
            )
            
            return {
                "gmail_creds": creds,
                "drive_creds": creds,  # Same credentials work for both
                "google_auth_complete": creds_data.get("google_auth_complete", False),
                "gmail_auth_complete": True,
                "drive_auth_complete": True
            }
        else:
            logger.warning(f"Invalid credentials format for user {username}")
            return None
    except Exception as e:
        logger.error(f"Error loading Google credentials for user {username}: {e}")
        return None

# Export commonly used secrets
ODOO_URL = get_secret("ODOO_URL")
ODOO_DB = get_secret("ODOO_DB")
ODOO_USERNAME = get_secret("ODOO_USERNAME")
ODOO_PASSWORD = get_secret("ODOO_PASSWORD")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
OPENAI_MODEL = get_secret("OPENAI_MODEL", "gpt-4")
DRIVE_PARENT_FOLDER_ID = get_secret("google.drive_parent_folder_id")
import streamlit as st
import os
import json
import logging
from typing import Optional, Dict, Any

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

# Export commonly used secrets
ODOO_URL = get_secret("ODOO_URL")
ODOO_DB = get_secret("ODOO_DB")
ODOO_USERNAME = get_secret("ODOO_USERNAME")
ODOO_PASSWORD = get_secret("ODOO_PASSWORD")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
OPENAI_MODEL = get_secret("OPENAI_MODEL", "gpt-4")
DRIVE_PARENT_FOLDER_ID = get_secret("google.drive_parent_folder_id")
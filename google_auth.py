import os
import json
import logging
import tempfile
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import get_secret, get_google_credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='google_auth.log'
)
logger = logging.getLogger(__name__)

# Define consistent scopes for all Google services
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly', 
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive.file'
]

def is_running_locally():
    """Definitive check for local environment"""
    local_auth = st.secrets.get('LOCAL_AUTH', 'False')
    return local_auth.lower() == 'true'

def get_redirect_uri():
    """Get the correct redirect URI based on environment"""
    if is_running_locally():
        logger.info("Using local redirect URI")
        return "http://localhost:8501/_oauth/callback"
    else:
        # More robust approach - try to detect the actual URL from Streamlit
        # For Streamlit Cloud, follow their protocol (https)
        base_url = "prezlab-tms.streamlit.app"
        redirect_uri = f"https://{base_url}/_oauth/callback"
        logger.info(f"Using deployed redirect URI: {redirect_uri}")
        return redirect_uri

# Modify google_auth.py to eliminate all OOB flow references

def get_google_service(service_name):
    """
    Unified function to get any Google service with proper authentication
    
    Args:
        service_name: Name of the service ('gmail' or 'drive')
        
    Returns:
        Service object or None if authentication fails
    """
    logger.info(f"Obtaining Google {service_name} service")
    
    # Check for existing credentials
    cred_key = f"google_{service_name}_creds"
    if cred_key in st.session_state:
        creds = st.session_state[cred_key]
        # Refresh token if expired
        if creds and hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
            try:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
                st.session_state[cred_key] = creds
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                # Clear invalid credentials
                st.session_state.pop(cred_key, None)
                creds = None
    else:
        creds = None
    
    # If no valid credentials, authenticate
    if not creds:
        try:
            client_config = get_google_credentials()
            if not client_config:
                logger.error("Google API credentials not found")
                st.error("Google API credentials are missing. Please check your configuration.")
                return None
            
            # Create a temporary file for credentials
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
                json.dump(client_config, temp)
                temp_path = temp.name
            
            try:
                # Get the appropriate redirect URI
                redirect_uri = get_redirect_uri()
                logger.info(f"Using redirect URI: {redirect_uri}")
                
                # Create flow with redirect URI
                flow = InstalledAppFlow.from_client_secrets_file(
                    temp_path, 
                    SCOPES,
                    redirect_uri=redirect_uri
                )
                
                # Check for authorization code in query parameters
                query_params = st.query_params()
                if "code" in query_params:
                    try:
                        code = query_params["code"][0]  # Use first code value
                        flow.fetch_token(code=code)
                        creds = flow.credentials
                        st.session_state[cred_key] = creds
                        st.session_state["auth_complete"] = True  # Set a flag instead of rerun
                        st.success("✅ Authentication successful!")
                    except Exception as e:
                        st.error(f"Authentication error: {str(e)}")
                        logger.error(f"OAuth token exchange error: {e}", exc_info=True)
                else:
                    # Initiate authorization flow
                    auth_url, _ = flow.authorization_url(
                        prompt='consent', 
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    st.info("### Google Authentication Required")
                    st.markdown(f"[Click here to authenticate with Google]({auth_url})")
                    return None
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
            
        except Exception as e:
            logger.error(f"Google Authentication Error: {e}", exc_info=True)
            st.error(f"Failed to authenticate with Google: {str(e)}")
            return None
    
    # Create and return the service
    if creds:
        try:
            # Use appropriate API version
            api_version = 'v3' if service_name == 'drive' else 'v1'
            service = build(service_name, api_version, credentials=creds)
            logger.info(f"Successfully created {service_name} service")
            return service
        except Exception as e:
            logger.error(f"Error creating {service_name} service: {e}")
            st.error(f"Error creating {service_name} service: {str(e)}")
            return None
    return None
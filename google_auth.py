import os
import json
import logging
import tempfile
import streamlit as st
import time
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
    logger.info(f"Getting Google {service_name} service")
    
    # First, check if we already have valid credentials for the service
    cred_key = f"google_{service_name}_creds"
    if cred_key in st.session_state and st.session_state[cred_key]:
        creds = st.session_state[cred_key]
        
        # Check if credentials are expired and need refresh
        if hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
            try:
                logger.info(f"Refreshing expired credentials for {service_name}")
                creds.refresh(Request())
                st.session_state[cred_key] = creds
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                # Don't delete credentials yet, try to use them anyway
        
        # Try to build the service with existing credentials
        try:
            api_version = 'v3' if service_name == 'drive' else 'v1'
            service = build(service_name, api_version, credentials=creds)
            logger.info(f"Successfully built {service_name} service using existing credentials")
            return service
        except Exception as e:
            logger.error(f"Error building {service_name} service with existing credentials: {e}")
            # Continue to authentication flow
    
    # Check if we should try the other service's credentials
    other_service = 'drive' if service_name == 'gmail' else 'gmail'
    other_cred_key = f"google_{other_service}_creds"
    
    if other_cred_key in st.session_state and st.session_state[other_cred_key]:
        # Try to use credentials from the other service (they should work for both)
        try:
            logger.info(f"Trying to use {other_service} credentials for {service_name}")
            creds = st.session_state[other_cred_key]
            api_version = 'v3' if service_name == 'drive' else 'v1'
            service = build(service_name, api_version, credentials=creds)
            
            # If successful, store these credentials for this service too
            st.session_state[cred_key] = creds
            logger.info(f"Successfully used {other_service} credentials for {service_name}")
            return service
        except Exception as e:
            logger.error(f"Error using {other_service} credentials for {service_name}: {e}")
            # Continue to authentication flow
    
    # If we reach here, we need to initiate the OAuth flow
    try:
        # Load client config from Streamlit secrets
        client_config_str = st.secrets["gcp"]["client_config"]
        if not client_config_str:
            logger.error("Google API client config not found in secrets")
            st.error("Google API credentials are missing. Please check your configuration.")
            return None
            
        client_config = json.loads(client_config_str)
        
        # Create a temporary file for credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
            json.dump(client_config, temp)
            temp_path = temp.name
        
        try:
            # Use a consistent redirect URI
            redirect_uri = "https://prezlab-tms.streamlit.app/"
            logger.info(f"Using redirect URI: {redirect_uri}")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                temp_path, 
                SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Generate authorization URL
            auth_url, _ = flow.authorization_url(
                prompt='consent', 
                access_type='offline',
                include_granted_scopes='true'
            )
            
            # Save service name being authenticated to session state
            st.session_state["authenticating_service"] = service_name
            
            # Prompt user to authenticate
            st.info(f"### Google Authentication Required")
            st.markdown(f"[Click here to authenticate with Google {service_name.capitalize()}]({auth_url})")
            
            # Add a cancel button
            if st.button("Cancel Authentication"):
                if "authenticating_service" in st.session_state:
                    del st.session_state["authenticating_service"]
                st.rerun()
            
            # Stop execution to wait for redirect
            st.stop()
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

def process_oauth_callback(code):
    """Process OAuth callback code without disrupting session state"""
    try:
        print(f"Processing OAuth code: {code[:10]}..." if len(code) > 10 else code)
        
        # Load client config from Streamlit secrets
        client_config_str = st.secrets["gcp"]["client_config"]
        client_config = json.loads(client_config_str)
        
        # Create a temporary file for credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
            json.dump(client_config, temp)
            temp_path = temp.name
        
        try:
            # Consistent redirect URI
            redirect_uri = "https://prezlab-tms.streamlit.app/"
            flow = InstalledAppFlow.from_client_secrets_file(
                temp_path, 
                SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Exchange code for token
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            # Store credentials for both services to avoid multiple auth
            st.session_state["google_gmail_creds"] = creds
            st.session_state["google_drive_creds"] = creds
            
            # Set all auth flags
            st.session_state["gmail_auth_complete"] = True
            st.session_state["drive_auth_complete"] = True
            st.session_state["google_auth_complete"] = True
            
            print("Authentication successful for all Google services!")
            return True
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
    except Exception as e:
        print(f"Error processing OAuth code: {e}")
        return False
    

def handle_oauth_callback(code):
    """Process Google OAuth callback code"""
    try:
        logger.info(f"Processing OAuth code: {code[:10]}..." if len(code) > 10 else code)
        
        # Load client config
        client_config_str = st.secrets["gcp"]["client_config"]
        client_config = json.loads(client_config_str)
        
        # Create a temporary file for credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
            json.dump(client_config, temp)
            temp_path = temp.name
        
        try:
            # Use the same URI that was used to initiate the flow
            redirect_uri = "https://prezlab-tms.streamlit.app/"
            
            flow = InstalledAppFlow.from_client_secrets_file(
                temp_path, 
                SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Exchange code for tokens
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            # Store credentials in session state for both services
            st.session_state["google_gmail_creds"] = creds
            st.session_state["google_drive_creds"] = creds
            
            # Set all auth flags
            st.session_state["gmail_auth_complete"] = True
            st.session_state["drive_auth_complete"] = True
            st.session_state["google_auth_complete"] = True
            
            # Save credentials for current user
            if st.session_state.get("logged_in") and st.session_state.get("user"):
                username = st.session_state.user.get("username")
                from config import save_user_google_creds
                google_creds = {
                    "gmail_creds": creds,
                    "drive_creds": creds,
                    "google_auth_complete": True
                }
                save_user_google_creds(username, google_creds)
                logger.info(f"Saved new Google credentials for user {username}")
            
            logger.info("Google authentication successful for all services")
            return True
        finally:
            # Clean up temporary file
            os.unlink(temp_path)
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}", exc_info=True)
        return False
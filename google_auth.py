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
    
    if "auth_attempts" not in st.session_state:
        st.session_state.auth_attempts = 0

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
                
                # Check for authorization code - using ONLY st.query_params (new API)
                if "code" in st.query_params:
                    try:
                        # Prevent infinite loops
                        st.session_state.auth_attempts += 1
                        if st.session_state.auth_attempts > 3:
                            st.error("Too many authentication attempts. Please reload the page and try again.")
                            st.session_state.pop("auth_attempts", None)
                            st.query_params.clear()
                            return None
                            
                        code = st.query_params["code"]
                        logger.info("Authorization code received from redirect")
                        
                        # Add timeout to token exchange
                        flow.fetch_token(code=code, timeout=30)  # Add 30 second timeout
                        creds = flow.credentials
                        st.session_state[cred_key] = creds
                        
                        # Clear session state counter and params
                        st.session_state.pop("auth_attempts", None)
                        st.query_params.clear()
                        
                        st.success("✅ Authentication successful!")
                        return build(service_name, api_version, credentials=creds)  # Return immediately instead of rerun
                    except Exception as e:
                        logger.error(f"Error exchanging code for token: {e}", exc_info=True)
                        st.error(f"Authentication error: {str(e)}")
                        st.query_params.clear()  # Clear params on error
                        st.session_state.pop("auth_attempts", None)
                        return None
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
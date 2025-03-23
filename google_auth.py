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
    """Unified function to get any Google service with proper authentication"""
    logger.info(f"Obtaining Google {service_name} service")
    
    # Debug information
    with st.expander("Authentication Debugging", expanded=False):
        st.write("Session state keys:", list(st.session_state.keys()))
        st.write("Query parameters:", dict(st.query_params))
    
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
                del st.session_state[cred_key]
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
                st.stop()
            
            # Create a temporary file for credentials
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
                json.dump(client_config, temp)
                temp_path = temp.name
            
            try:
                # HARDCODE the redirect URI to match exactly what's in Google Cloud Console
                redirect_uri = "https://prezlab-tms.streamlit.app/_oauth/callback"
                logger.info(f"Using redirect URI: {redirect_uri}")
                
                # Create flow with explicit redirect URI
                flow = InstalledAppFlow.from_client_secrets_file(
                    temp_path, 
                    SCOPES,
                    redirect_uri=redirect_uri
                )
                
                # Check for authorization code
                if "code" in st.query_params:
                    try:
                        code = st.query_params["code"]
                        logger.info(f"Processing auth code: {code[:10]}...")
                        
                        # Exchange code for token
                        flow.fetch_token(code=code)
                        creds = flow.credentials
                        st.session_state[cred_key] = creds
                        
                        # Clean up URL - use try/except for compatibility
                        try:
                            st.set_query_params()
                        except:
                            try:
                                st.query_params.clear()
                            except:
                                pass
                        
                        logger.info("Authentication successful!")
                        st.success("✅ Authentication successful!")
                        time.sleep(1)  # Give UI time to update
                        
                        # Create service immediately
                        api_version = 'v3' if service_name == 'drive' else 'v1'
                        service = build(service_name, api_version, credentials=creds)
                        return service
                    except Exception as e:
                        logger.error(f"Error exchanging code for token: {e}", exc_info=True)
                        st.error(f"Authentication error: {str(e)}")
                        if cred_key in st.session_state:
                            del st.session_state[cred_key]
                        st.stop()
                else:
                    # Initiate authorization flow
                    auth_url, _ = flow.authorization_url(
                        prompt='consent', 
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    st.info("### Google Authentication Required")
                    st.markdown(f"[Click here to authenticate with Google]({auth_url})")
                    st.stop()  # Important: stop execution here
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
        except Exception as e:
            logger.error(f"Google Authentication Error: {e}", exc_info=True)
            st.error(f"Failed to authenticate with Google: {str(e)}")
            st.stop()
    
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
            if cred_key in st.session_state:
                del st.session_state[cred_key]
            st.stop()
    return None
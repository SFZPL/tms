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
    print(f"Obtaining Google {service_name} service")
    
    # Check for existing credentials
    cred_key = f"google_{service_name}_creds"
    if cred_key in st.session_state:
        creds = st.session_state[cred_key]
        # Refresh token if expired
        if creds and hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
            try:
                print("Refreshing expired credentials")
                creds.refresh(Request())
                st.session_state[cred_key] = creds
            except Exception as e:
                print(f"Failed to refresh credentials: {e}")
                # Clear invalid credentials
                if cred_key in st.session_state:
                    del st.session_state[cred_key]
                creds = None
    else:
        creds = None
    
    # If no valid credentials, authenticate
    if not creds:
        try:
            # Load client config from Streamlit secrets
            try:
                client_config_str = st.secrets["gcp"]["client_config"]
                client_config = json.loads(client_config_str)
            except Exception as e:
                print(f"Error loading client config: {e}")
                st.error("Google API credentials are missing. Please check your configuration.")
                return None
            
            # Create a temporary file for credentials
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp:
                json.dump(client_config, temp)
                temp_path = temp.name
            
            try:
                # CRITICAL: Use the base app URL without _oauth/callback
                redirect_uri = "https://prezlab-tms.streamlit.app/"
                st.info(f"Using redirect URI: {redirect_uri}")
                
                # Create flow with redirect URI
                flow = InstalledAppFlow.from_client_secrets_file(
                    temp_path, 
                    SCOPES,  # Use the comprehensive list defined at the top of the file
                    redirect_uri=redirect_uri
                )
                
                # Check for authorization code in query parameters
                if "code" in st.query_params:
                    try:
                        code = st.query_params["code"]
                        print(f"Authorization code received")
                        
                        # Exchange code for token
                        flow.fetch_token(code=code)
                        creds = flow.credentials
                        st.session_state[cred_key] = creds
                        
                        # Clean up URL
                        try:
                            st.set_query_params()
                        except:
                            pass
                        
                        print("Authentication successful!")
                        st.success("✅ Authentication successful!")
                        time.sleep(1)  # Give UI time to update
                        st.rerun()  # Rerun to clear URL parameters
                    except Exception as e:
                        print(f"Error exchanging code for token: {e}")
                        st.error(f"Authentication error: {str(e)}")
                        if cred_key in st.session_state:
                            del st.session_state[cred_key]
                        st.stop()  # CRITICAL: Stop execution on error
                else:
                    # Initiate authorization flow
                    auth_url, _ = flow.authorization_url(
                        prompt='consent', 
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    st.info("### Google Authentication Required")
                    st.markdown(f"[Click here to authenticate with Google]({auth_url})")
                    st.stop()  # CRITICAL: Stop execution here
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    print(f"Failed to delete temporary file: {e}")
        except Exception as e:
            print(f"Google Authentication Error: {e}")
            st.error(f"Failed to authenticate with Google: {str(e)}")
            st.stop()  # Stop execution on error
    
    # Create and return the service
    if creds:
        try:
            # Use appropriate API version
            api_version = 'v3' if service_name == 'drive' else 'v1'
            service = build(service_name, api_version, credentials=creds)
            print(f"Successfully created {service_name} service")
            return service
        except Exception as e:
            print(f"Error creating {service_name} service: {e}")
            st.error(f"Error creating {service_name} service: {str(e)}")
            if cred_key in st.session_state:
                del st.session_state[cred_key]
            return None
    return None
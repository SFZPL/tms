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
    print(f"Obtaining Google {service_name} service")
    
    # Check for authorization code in query parameters FIRST
    if "code" in st.query_params:
        try:
            code = st.query_params["code"]
            print(f"Authorization code received: {code[:10]}..." if len(code) > 10 else code)
            
            # Save the code and clear query params to prevent reuse
            code_value = code
            st.query_params.clear()
            
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
                # Create flow with redirect URI
                redirect_uri = "https://prezlab-tms.streamlit.app/"
                flow = InstalledAppFlow.from_client_secrets_file(
                    temp_path, 
                    SCOPES,
                    redirect_uri=redirect_uri
                )
                
                # Exchange code for token
                try:
                    flow.fetch_token(code=code_value)
                    creds = flow.credentials
                    
                    # Store credentials in session state
                    cred_key = f"google_{service_name}_creds"
                    st.session_state[cred_key] = creds
                    
                    # Set backup auth completion flags
                    st.session_state[f"{service_name}_auth_complete"] = True
                    
                    print(f"Authentication successful for {service_name}!")
                    st.success(f"✅ Authentication successful for {service_name}!")
                    
                    # Create and return service
                    api_version = 'v3' if service_name == 'drive' else 'v1'
                    service = build(service_name, api_version, credentials=creds)
                    return service
                except Exception as e:
                    print(f"Error exchanging code: {e}")
                    if "invalid_grant" in str(e).lower():
                        st.error("Authorization code expired or invalid. Please try again.")
                    else:
                        st.error(f"Authentication error: {str(e)}")
                    
                    # Clean up session state on failure
                    for key in [f"google_{service_name}_creds", f"{service_name}_auth_complete"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    return None
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    print(f"Failed to delete temporary file: {e}")
        except Exception as e:
            print(f"Error processing authorization code: {e}")
            st.error(f"Error processing authorization code: {str(e)}")
            return None
    
    # If we reach here, we don't have a code, so check for existing credentials
    cred_key = f"google_{service_name}_creds"
    if cred_key in st.session_state:
        creds = st.session_state[cred_key]
        # Refresh token if expired
        if creds and hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
            try:
                print(f"Refreshing expired credentials for {service_name}")
                creds.refresh(Request())
                st.session_state[cred_key] = creds
                
                # Mark as authenticated
                st.session_state[f"{service_name}_auth_complete"] = True
            except Exception as e:
                print(f"Failed to refresh credentials: {e}")
                # Clear invalid credentials
                for key in [cred_key, f"{service_name}_auth_complete"]:
                    if key in st.session_state:
                        del st.session_state[key]
                creds = None
    else:
        creds = None
    
    # If we have valid credentials, build and return the service
    if creds:
        try:
            api_version = 'v3' if service_name == 'drive' else 'v1'
            service = build(service_name, api_version, credentials=creds)
            print(f"Successfully created {service_name} service using existing credentials")
            return service
        except Exception as e:
            print(f"Error creating {service_name} service: {e}")
            st.error(f"Error creating {service_name} service: {str(e)}")
            
            # Clear invalid credentials
            for key in [cred_key, f"{service_name}_auth_complete"]:
                if key in st.session_state:
                    del st.session_state[key]
            
            return None
    
    # If we reach here, we need to initiate authentication flow
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
            # Create flow with redirect URI
            redirect_uri = "https://prezlab-tms.streamlit.app/"
            
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
            
            # Prompt user to authenticate
            st.info(f"### {service_name.capitalize()} Authentication Required")
            st.markdown(f"[Click here to authenticate with Google {service_name.capitalize()}]({auth_url})")
            
            # Stop execution to wait for redirect
            st.stop()
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                print(f"Failed to delete temporary file: {e}")
    except Exception as e:
        print(f"Google Authentication Error: {e}")
        st.error(f"Failed to authenticate with Google: {str(e)}")
    
    return None
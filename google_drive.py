import os
import pickle
import logging
import streamlit as st
import json
import tempfile
# Add at the top of both gmail_integration.py and google_drive.py
import time
from pathlib import Path
from typing import Optional, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import get_secret, get_google_credentials  # Import from centralized config

# Add to the top of google_drive.py and gmail_integration.py
from streamlit.components.v1 import components

def streamlit_auth_flow(flow):
    """Performs OAuth flow using Streamlit's components API"""
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    # Display authentication instructions
    st.markdown("### Google Authentication Required")
    st.warning("You need to authenticate with Google to access Drive/Gmail.")
    
    # Create an iframe for authentication
    auth_component = components.iframe(auth_url, height=500, scrolling=True)
    
    # Get the authorization code from the user
    auth_code = st.text_input("After completing authentication, enter the code shown:")
    
    if auth_code:
        try:
            flow.fetch_token(code=auth_code)
            return flow.credentials
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return None
    return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='google_drive.log'
)
logger = logging.getLogger(__name__)

# Define Google Drive API scopes
# Use identical SCOPES in both files
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly', 
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive.file'
]

# Get parent folder ID from config
PARENT_FOLDER_ID = get_secret("google.drive_parent_folder_id", "")

def get_streamlit_oauth_flow(credentials_dict, scopes):
    """
    Creates an OAuth flow compatible with Streamlit deployments.
    
    Args:
        credentials_dict: Dictionary containing credentials
        scopes: List of API scopes to request
        
    Returns:
        Properly configured flow object
    """
    import json
    import tempfile
    from google_auth_oauthlib.flow import Flow
    
    # Create a temporary file for the credentials
    with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as temp:
        json.dump(credentials_dict, temp)
        temp_path = temp.name
    
    try:
        # For Streamlit Cloud, use redirect approach
        if "STREAMLIT_SHARING_MODE" in os.environ or "STREAMLIT_SERVER_URL" in os.environ:
            # Get the base URL for the current app
            base_url = st.secrets.get("STREAMLIT_SERVER_URL", "http://localhost:8501")
            redirect_uri = f"{base_url}/_oauth/callback"
            
            # Make sure this redirect URI is authorized in your Google Cloud Console
            flow = Flow.from_client_secrets_file(
                temp_path,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
        else:
            # Local development can use local server
            flow = Flow.from_client_secrets_file(
                temp_path,
                scopes=scopes,
                redirect_uri="http://localhost:8501/_oauth/callback"
            )
            
        return flow
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"Error removing temporary credentials file: {e}")
            
    return None

def get_drive_service() -> Optional[Any]:
    """
    Authenticates with Google Drive API using appropriate flow based on environment.
    Works in both deployed Streamlit and local development.
    """
    # Debug info
    with st.expander("Drive Authentication Debugging", expanded=False):
        st.write("Session state keys:", list(st.session_state.keys()))
        st.write("Query parameters:", st.query_params)
    
    # Check if we already have credentials
    if "drive_credentials" in st.session_state:
        creds = st.session_state.drive_credentials
        # Refresh token if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                st.session_state.drive_credentials = creds
                logger.info("Drive credentials refreshed successfully")
            except Exception as e:
                logger.error(f"Error refreshing Drive credentials: {e}")
                del st.session_state.drive_credentials
                st.rerun()
    else:
        # Load client config
        try:
            client_config = get_google_credentials()
            if not client_config:
                logger.error("Google API credentials not found")
                st.error("Google Drive credentials not found. Check configuration.")
                return None
            
            # Create a temporary file for the credentials
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp:
                temp.write(json.dumps(client_config).encode("utf-8"))
                temp_path = temp.name
            
            try:
                # Detect environment (local vs deployed)
                is_local = is_running_locally()
                
                if is_local:
                    # Local development: use local server approach
                    st.info("Running in local development mode. Using local OAuth flow.")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        temp_path, 
                        SCOPES
                    )
                    # Display a message explaining what will happen
                    st.info("A browser window will open to complete authentication.")
                    creds = flow.run_local_server(port=0)
                    st.session_state.drive_credentials = creds
                    st.success("Authentication completed! You can now use Google Drive.")
                else:
                    # Deployed environment: use redirect URI approach
                    # Get the deployment URL
                    base_url = get_deployed_url()
                    redirect_uri = f"{base_url}"  # No trailing slash or path
                    
                    logger.info(f"Using redirect URI for Drive: {redirect_uri}")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        temp_path, 
                        SCOPES,
                        redirect_uri=redirect_uri
                    )
                    
                    # Check for authorization code in query parameters
                    query_params = st.query_params
                    if "code" in query_params:
                        try:
                            code = query_params["code"]
                            logger.info("Exchanging code for token...")
                            flow.fetch_token(code=code)
                            st.session_state.drive_credentials = flow.credentials
                            
                            # Clean up the URL
                            try:
                                st.set_query_params()
                            except:
                                pass
                                
                            st.success("Google Drive authentication successful!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            logger.error(f"Error exchanging code: {e}")
                            st.error(f"Authentication error: {str(e)}")
                            auth_url, _ = flow.authorization_url(prompt='consent')
                            st.markdown(f"[Click here to try again]({auth_url})")
                            return None
                    else:
                        # Start the auth flow
                        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
                        st.warning("Authentication required for Google Drive access.")
                        st.markdown(f"[Click here to authenticate with Google Drive]({auth_url})")
                        return None
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Error removing temp file: {e}")
                
        except Exception as e:
            logger.error(f"Error in Drive authentication setup: {e}")
            st.error(f"Error setting up Drive authentication: {str(e)}")
            return None

    try:
        # Build and return Drive service
        service = build('drive', 'v3', credentials=st.session_state.drive_credentials)
        logger.info("Google Drive service created successfully")
        return service
        
    except Exception as e:
        logger.error(f"Error building Google Drive service: {e}")
        st.error(f"Error connecting to Google Drive: {str(e)}")
        if "drive_credentials" in st.session_state:
            del st.session_state.drive_credentials
        return None

def is_running_locally():
    """Check if the app is running locally or deployed."""
    # Several approaches to detect local vs deployed environment
    
    # Approach 1: Check for environment variables set in Streamlit Cloud
    if os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("STREAMLIT_SERVER_URL"):
        return False
    
    # Approach 2: Try to detect localhost in STREAMLIT_SERVER_ADDRESS
    server_address = os.environ.get("STREAMLIT_SERVER_ADDRESS", "")
    if "localhost" in server_address or "127.0.0.1" in server_address:
        return True
        
    # Default to assuming we're in a deployed environment if unsure
    # You can customize this logic based on your specific deployment
    return False

def get_deployed_url():
    """Get the base URL for the deployed Streamlit app."""
    # For Streamlit Cloud, try to get from environment
    if "STREAMLIT_SERVER_URL" in os.environ:
        return os.environ["STREAMLIT_SERVER_URL"]
    
    # If in secrets
    if hasattr(st.secrets, "STREAMLIT_SERVER_URL"):
        return st.secrets.STREAMLIT_SERVER_URL
    
    # Fallback - you should set this in your secrets.toml
    return st.secrets.get("deployed_url", "https://prezlab-tms.streamlit.app/")


def create_folder(folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
    """
    Creates a folder in Google Drive.
    
    Args:
        folder_name: Name of the folder to create
        parent_folder_id: ID of the parent folder (optional)
        
    Returns:
        Folder ID if successful, None otherwise
    """
    if not folder_name:
        logger.error("Folder name is required")
        return None
    
    service = get_drive_service()
    if not service:
        logger.error("Google Drive service not initialized")
        return None
    
    try:
        # Use the specified parent folder ID or the default one from environment
        parent_id = parent_folder_id or PARENT_FOLDER_ID
        
        # Set up folder metadata
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        # Add parent folder if specified
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        # Create the folder
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        folder_id = folder.get('id')
        logger.info(f"Created folder: {folder_name} (ID: {folder_id})")
        return folder_id
        
    except Exception as e:
        logger.error(f"Error creating folder: {e}", exc_info=True)
        return None

def get_folder_link(folder_id: str) -> Optional[str]:
    """
    Gets the web link to a Google Drive folder.
    
    Args:
        folder_id: ID of the folder
        
    Returns:
        URL to the folder if successful, None otherwise
    """
    if not folder_id:
        logger.error("Folder ID is required")
        return None
    
    return f"https://drive.google.com/drive/folders/{folder_id}"

def get_folder_url(folder_id: str) -> Optional[str]:
    """
    Gets a shareable URL for the folder.
    
    Args:
        folder_id: ID of the folder
        
    Returns:
        Shareable URL if successful, None otherwise
    """
    service = get_drive_service()
    if not service or not folder_id:
        return None
    
    try:
        # Get permissions for the folder
        permission = {
            'type': 'anyone',
            'role': 'reader',
            'allowFileDiscovery': True
        }
        
        service.permissions().create(
            fileId=folder_id,
            body=permission
        ).execute()
        
        return f"https://drive.google.com/drive/folders/{folder_id}"
        
    except Exception as e:
        logger.error(f"Error creating shareable link: {e}", exc_info=True)
        return None
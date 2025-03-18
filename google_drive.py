import os
import pickle
import logging
import streamlit as st
import json
import tempfile
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
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/drive.file']

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
    Authenticates with Google Drive API and returns a service object.
    Uses session state instead of token files for Streamlit Cloud.
    """
    try:
        # Try to get credentials from session state
        creds = st.session_state.get("drive_credentials", None)
        
        # Check if credentials need to be refreshed or created
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.info("Creating new credentials")
                
                # Get credentials dictionary
                credentials_dict = get_google_credentials()
                if not credentials_dict:
                    logger.error("No credentials available")
                    st.error("Google Drive credentials not found. Check configuration.")
                    return None
                
                # For Streamlit Cloud, we need a different auth approach
                # This works for cloud environments where we can't run a local server
                if st.runtime.exists():  # Check if we're running in Streamlit
                    # Create a temporary file for the credentials
                    with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as temp:
                        json.dump(credentials_dict, temp)
                        temp_path = temp.name
                    
                    try:
                        # Create flow with a headless redirect
                        flow = InstalledAppFlow.from_client_secrets_file(
                            temp_path, 
                            SCOPES,
                            redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Use out-of-band authentication
                        )
                        
                        # Generate the authorization URL
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        
                        # Display instructions to the user
                        st.info("Authentication required for Google Drive access.")
                        st.markdown(f"1. Click this link to authorize: [Authorize Drive Access]({auth_url})")
                        st.markdown("2. Sign in and grant permission")
                        st.markdown("3. Copy the authorization code")
                        
                        # Get the authorization code from the user
                        auth_code = st.text_input("Enter the authorization code for Drive:", key="drive_auth_code")
                        
                        if auth_code:
                            # Exchange the authorization code for credentials
                            flow.fetch_token(code=auth_code)
                            creds = flow.credentials
                            st.success("Google Drive authentication successful!")
                        else:
                            # No auth code yet, return None
                            return None
                    finally:
                        # Clean up the temporary file
                        try:
                            os.unlink(temp_path)
                        except Exception as e:
                            logger.warning(f"Error removing temporary credentials file: {e}")
                else:
                    # Local development: use local server approach
                    # Create a temporary file for the credentials
                    with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as temp:
                        json.dump(credentials_dict, temp)
                        temp_path = temp.name
                    
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(temp_path, SCOPES)
                        creds = flow.run_local_server(port=0)
                    finally:
                        # Clean up the temporary file
                        try:
                            os.unlink(temp_path)
                        except Exception as e:
                            logger.warning(f"Error removing temporary credentials file: {e}")
            
            # Save credentials to session state
            st.session_state["drive_credentials"] = creds
        
        # Build and return Drive service
        service = build('drive', 'v3', credentials=creds)
        logger.info("Google Drive service created successfully")
        return service
        
    except Exception as e:
        logger.error(f"Error creating Google Drive service: {e}", exc_info=True)
        st.error(f"Error connecting to Google Drive: {str(e)}")
        return None


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
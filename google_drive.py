import logging
import streamlit as st
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from config import get_secret

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='google_drive.log'
)
logger = logging.getLogger(__name__)

# Get parent folder ID from config
PARENT_FOLDER_ID = get_secret("google.drive_parent_folder_id", "")

def get_drive_service():
    """Get an authenticated Drive service"""
    from google_auth import get_google_service
    
    # Check if we already have Drive credentials
    if "google_drive_creds" in st.session_state:
        # Use existing Drive credentials
        return build('drive', 'v3', credentials=st.session_state.google_drive_creds)
    
    # Get service through standard flow
    return get_google_service('drive')

def create_folder(folder_name, parent_folder_id=None):
    """
    Creates a folder in Google Drive.
    
    Args:
        folder_name: Name of the folder to create
        parent_folder_id: ID of the parent folder (optional)
        
    Returns:
        Folder ID if successful, None otherwise
    """

    cache_key = f"drive_folder_{folder_name}"
    if cache_key in st.session_state:
        print(f"Using cached folder ID for {folder_name}")
        return st.session_state[cache_key]
    
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
        # Store successful folder creation
        if folder_id:
            st.session_state[cache_key] = folder_id
        
        return folder_id
        
    except Exception as e:
        logger.error(f"Error creating folder: {e}", exc_info=True)
        return None
    

def get_folder_link(folder_id):
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

def get_folder_url(folder_id):
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
import os
import json
import logging
import pickle
import base64

import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import get_google_credentials, supabase

# Configure logging
debug_logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='google_auth.log'
)

# OAuth scopes for Gmail and Drive
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive.file'
]


def get_redirect_uri():
    """
    Returns the correct redirect URI based on environment.
    """
    # Local testing environment
    if os.getenv('LOCAL_AUTH', 'False').lower() == 'true':
        debug_logger.info("Using local redirect URI")
        return 'http://localhost:8501/_oauth/callback'
    # Deployed environment: use domain from secrets
    base_url = st.secrets.get('app', {}).get('host', 'YOUR_DEPLOYED_APP_DOMAIN')
    redirect_uri = f"https://{base_url}/_oauth/callback"
    debug_logger.info(f"Using deployed redirect URI: {redirect_uri}")
    return redirect_uri


def _load_creds(username: str, service: str):
    """
    Load pickled credentials for a given user+service from Supabase.
    Returns None if not found or on error.
    """
    try:
        resp = (
            supabase
            .from_('oauth_tokens')
            .select('token')
            .eq('username', username)
            .eq('service', service)
            .single()
            .execute()
        )
        data = resp.data
        if not data or 'token' not in data:
            return None
        raw = base64.b64decode(data['token'])
        creds = pickle.loads(raw)
        return creds
    except Exception as e:
        debug_logger.warning(f"Failed to load credentials for {username}/{service}: {e}")
        return None


def _save_creds(username: str, service: str, creds):
    """
    Serialize and upsert credentials into Supabase for future use.
    """
    try:
        raw = pickle.dumps(creds)
        b64 = base64.b64encode(raw).decode()
        record = {'username': username, 'service': service, 'token': b64}
        supabase.from_('oauth_tokens').upsert(record, on_conflict=['username','service']).execute()
    except Exception as e:
        debug_logger.error(f"Failed to save credentials for {username}/{service}: {e}")


def get_google_service(service_name: str):
    """
    Return a Google API service client (Gmail or Drive), persisting OAuth tokens per app user.
    """
    # Ensure user is logged in
    user = st.session_state.get('user')
    username = user.get('username') if isinstance(user, dict) else None
    if not username:
        st.error('User not logged in; cannot authenticate Google service.')
        return None

    # 1) Try loading existing credentials
    creds = _load_creds(username, service_name)
    if creds:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_creds(username, service_name, creds)
        st.session_state[f'google_{service_name}_creds'] = creds
        api_version = 'v1' if service_name == 'gmail' else 'v3'
        return build(service_name, api_version, credentials=creds)

    # 2) No saved creds: for server environment, provide instructions
    client_config = get_google_credentials()
    if not client_config:
        st.error('Google OAuth client configuration missing.')
        return None

    try:
        # First try the local server approach
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=get_redirect_uri()
        )
        
        # Detect if we're in a browserless environment
        try:
            import webbrowser
            browser = webbrowser.get()
            creds = flow.run_local_server(port=0)
        except Exception as e:
            # If browser can't be found, provide instructions for manual auth
            auth_url = flow.authorization_url()[0]
            st.error("Cannot automatically open a browser in this environment.")
            st.info(f"""
            ### Manual Authentication Required
            
            Please complete these steps:
            
            1. Open this URL in a browser: [Authentication Link]({auth_url})
            2. Log in with your Google account and grant the requested permissions
            3. Copy the authorization code from the browser
            4. Enter the code below
            """)
            auth_code = st.text_input("Enter the authorization code:", key="auth_code_input")
            if auth_code:
                try:
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    st.success("Authentication successful!")
                except Exception as auth_err:
                    st.error(f"Authentication failed: {auth_err}")
                    return None
            else:
                return None  # No credentials yet

        # Persist and return
        _save_creds(username, service_name, creds)
        st.session_state[f'google_{service_name}_creds'] = creds
        api_version = 'v1' if service_name == 'gmail' else 'v3'
        return build(service_name, api_version, credentials=creds)
    
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

def handle_oauth_callback(auth_code):
    """
    Process the OAuth callback code
    
    Args:
        auth_code: The authorization code from the callback
        
    Returns:
        True if successful, False otherwise
    """
    try:
        debug_logger.info(f"Processing OAuth callback code")
        client_config = get_google_credentials()
        
        if not client_config:
            debug_logger.error("Missing Google client configuration")
            return False
            
        # Create flow with the same parameters as the original request
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=get_redirect_uri()
        )
        
        # Exchange code for credentials
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        
        # Store credentials for both services
        # Default to using same credentials for both services
        username = st.session_state.get('user', {}).get('username', 'default_user')
        _save_creds(username, 'gmail', creds)
        _save_creds(username, 'drive', creds)
        
        # Update session state
        st.session_state['google_gmail_creds'] = creds
        st.session_state['google_drive_creds'] = creds
        
        debug_logger.info("OAuth callback processed successfully")
        return True
    except Exception as e:
        debug_logger.error(f"Error processing OAuth callback: {e}")
        return False
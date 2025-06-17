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
    import json
    import uuid
    import tempfile
    import os
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    
    try:
        from token_storage import get_user_token, save_user_token
    except ImportError:
        logger.warning("token_storage module not available, persistence disabled")
        get_user_token = lambda username, service: None
        save_user_token = lambda username, service, token: False
    
    logger.info(f"Getting Google {service_name} service")
    
    # STEP 1: Check if we have credentials in current session
    cred_key = f"google_{service_name}_creds"
    if cred_key in st.session_state and st.session_state[cred_key]:
        creds = st.session_state[cred_key]
        
        # Check if credentials are expired and need refresh
        if hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
            try:
                logger.info(f"Refreshing expired credentials for {service_name}")
                creds.refresh(Request())
                st.session_state[cred_key] = creds
                
                # Save refreshed token back to database if user is logged in
                if "user" in st.session_state and st.session_state.user:
                    username = st.session_state.user.get("username")
                    if username:
                        creds_dict = {
                            'token': creds.token,
                            'refresh_token': creds.refresh_token,
                            'token_uri': creds.token_uri,
                            'client_id': creds.client_id,
                            'client_secret': creds.client_secret,
                            'scopes': creds.scopes
                        }
                        save_user_token(username, f"google_{service_name}", creds_dict)
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                # Continue to next auth method - don't delete the credentials yet
                pass
        
        # Try to build service with existing credentials
        if not hasattr(creds, 'expired') or not creds.expired:
            try:
                api_version = 'v3' if service_name == 'drive' else 'v1'
                service = build(service_name, api_version, credentials=creds)
                logger.info(f"Successfully built {service_name} service using session credentials")
                return service
            except Exception as e:
                logger.error(f"Error building {service_name} service with session credentials: {e}")
                # Continue to next authentication method
    
    # STEP 2: Check if user is logged in and has stored tokens
    if "user" in st.session_state and st.session_state.user:
        username = st.session_state.user.get("username")
        if username:
            # Try to get saved token from database
            saved_token = get_user_token(username, f"google_{service_name}")
            
            if saved_token:
                try:
                    # Create credentials from saved token
                    creds = Credentials(
                        token=saved_token.get('token'),
                        refresh_token=saved_token.get('refresh_token'),
                        token_uri=saved_token.get('token_uri'),
                        client_id=saved_token.get('client_id'),
                        client_secret=saved_token.get('client_secret'),
                        scopes=saved_token.get('scopes')
                    )
                    
                    # Check if credentials are expired and need refresh
                    if hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
                        logger.info(f"Refreshing expired credentials from database for {service_name}")
                        creds.refresh(Request())
                        
                        # Save refreshed token back to database
                        creds_dict = {
                            'token': creds.token,
                            'refresh_token': creds.refresh_token,
                            'token_uri': creds.token_uri,
                            'client_id': creds.client_id,
                            'client_secret': creds.client_secret,
                            'scopes': creds.scopes
                        }
                        save_user_token(username, f"google_{service_name}", creds_dict)
                    
                    # Store in session state for convenience
                    st.session_state[cred_key] = creds
                    
                    # Set auth flags
                    st.session_state[f"{service_name}_auth_complete"] = True
                    if "google_gmail_creds" in st.session_state and "google_drive_creds" in st.session_state:
                        st.session_state["google_auth_complete"] = True
                    
                    # Build service
                    api_version = 'v3' if service_name == 'drive' else 'v1'
                    service = build(service_name, api_version, credentials=creds)
                    logger.info(f"Successfully built {service_name} service using saved credentials")
                    return service
                except Exception as e:
                    logger.error(f"Error using saved token from database: {e}")
                    # Continue to OAuth flow
    
    # STEP 3: If we need to authenticate, set up the OAuth flow
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
            # Generate a state token to prevent CSRF
            state = str(uuid.uuid4())
            st.session_state["oauth_state"] = state
            
            # Save what we're authenticating for
            st.session_state["authenticating_service"] = service_name
            
            # Use a consistent redirect URI
            redirect_uri = "https://prezlab-tms.streamlit.app/"
            logger.info(f"Using redirect URI: {redirect_uri}")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                temp_path, 
                SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Generate authorization URL with state parameter
            auth_url, _ = flow.authorization_url(
                prompt='consent', 
                access_type='offline',
                state=state,
                include_granted_scopes='true'
            )
            
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
    

# In google_auth.py - handle_oauth_callback function
def handle_oauth_callback(code):
    """Process Google OAuth callback code with simplified approach"""
    try:
        logger.info(f"Processing OAuth code")
        
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
            
            # Import and save to Supabase
            print("SAVING TOKEN TO SUPABASE - DIRECT TEST")
            try:
                from token_storage import save_user_token
                
                if "user" in st.session_state and st.session_state.user:
                    username = st.session_state.user.get("username")
                    if username:
                        # Convert credentials to serializable format
                        creds_dict = {
                            'token': creds.token,
                            'refresh_token': creds.refresh_token,
                            'token_uri': creds.token_uri,
                            'client_id': creds.client_id,
                            'client_secret': creds.client_secret,
                            'scopes': creds.scopes
                        }
                        
                        # Direct save attempt - add custom print statements
                        print(f"Token saving attempt for {username}/google_gmail")
                        result = save_user_token(username, "google_gmail", creds_dict)
                        print(f"Save result: {result}")
                        
                        # Also save for Drive
                        print(f"Token saving attempt for {username}/google_drive")
                        result = save_user_token(username, "google_drive", creds_dict)
                        print(f"Save result: {result}")
                    else:
                        print("ERROR: Username not found in session state")
                else:
                    print("ERROR: User information not found in session state")
            except Exception as e:
                print(f"ERROR saving token: {str(e)}")
                import traceback
                print(traceback.format_exc())
            
            logger.info("Google authentication successful")
            return True
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}", exc_info=True)
        return False
    
def auto_authenticate_google_services():
    """
    Automatically authenticate Google services if saved credentials exist.
    Called after user login.
    """
    logger.info("Attempting auto-authentication for Google services")
    
    # Check if user is logged in and has username
    if "user" not in st.session_state or not st.session_state.user:
        logger.info("No user logged in, skipping auto-authentication")
        return False
    
    username = st.session_state.user.get("username")
    if not username:
        logger.info("No username found, skipping auto-authentication")
        return False
    
    try:
        from token_storage import get_user_token
        
        # Track success
        gmail_success = False
        drive_success = False
        
        # Try to authenticate Gmail
        gmail_token = get_user_token(username, "google_gmail")
        if gmail_token:
            try:
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=gmail_token.get('token'),
                    refresh_token=gmail_token.get('refresh_token'),
                    token_uri=gmail_token.get('token_uri'),
                    client_id=gmail_token.get('client_id'),
                    client_secret=gmail_token.get('client_secret'),
                    scopes=gmail_token.get('scopes')
                )
                
                # Check if expired and refresh if needed
                if hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    
                    # Save refreshed token
                    from token_storage import save_user_token
                    creds_dict = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    }
                    save_user_token(username, "google_gmail", creds_dict)
                
                # Store in session state
                st.session_state["google_gmail_creds"] = creds
                st.session_state["gmail_auth_complete"] = True
                gmail_success = True
                logger.info("Gmail auto-authentication successful")
                
            except Exception as e:
                logger.error(f"Error auto-authenticating Gmail: {e}")
        
        # Try to authenticate Drive
        drive_token = get_user_token(username, "google_drive")
        if drive_token:
            try:
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=drive_token.get('token'),
                    refresh_token=drive_token.get('refresh_token'),
                    token_uri=drive_token.get('token_uri'),
                    client_id=drive_token.get('client_id'),
                    client_secret=drive_token.get('client_secret'),
                    scopes=drive_token.get('scopes')
                )
                
                # Check if expired and refresh if needed
                if hasattr(creds, 'expired') and creds.expired and hasattr(creds, 'refresh_token'):
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    
                    # Save refreshed token
                    from token_storage import save_user_token
                    creds_dict = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    }
                    save_user_token(username, "google_drive", creds_dict)
                
                # Store in session state
                st.session_state["google_drive_creds"] = creds
                st.session_state["drive_auth_complete"] = True
                drive_success = True
                logger.info("Drive auto-authentication successful")
                
            except Exception as e:
                logger.error(f"Error auto-authenticating Drive: {e}")
        
        # Set overall auth complete if both services authenticated
        if gmail_success and drive_success:
            st.session_state["google_auth_complete"] = True
            logger.info("Both Google services auto-authenticated successfully")
            return True
        elif gmail_success or drive_success:
            logger.info(f"Partial auto-authentication: Gmail={gmail_success}, Drive={drive_success}")
            return True
        else:
            logger.info("No saved credentials found for auto-authentication")
            return False
            
    except Exception as e:
        logger.error(f"Error in auto_authenticate_google_services: {e}")
        return False
import os
import pickle
import base64
import logging
import json
# Add at the top of both gmail_integration.py and google_drive.py
import time
import tempfile
import streamlit as st
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config import get_secret, get_google_credentials  # Import from centralized config
from google_drive import is_running_locally, get_deployed_url

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
    filename='gmail_integration.log'
)
logger = logging.getLogger(__name__)

# Define constants
# Use identical SCOPES in both files
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly', 
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive.file'
]
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

def get_gmail_service():
    """Enhanced Gmail service authentication with detailed logging"""
    st.write("Starting Gmail Authentication")
    
    # Clear existing credentials if they seem problematic
    if "gmail_credentials" in st.session_state:
        st.write("Existing Gmail credentials found. Checking validity...")
        
        # Add more validation checks
        creds = st.session_state.gmail_credentials
        
        if not creds or not hasattr(creds, 'valid'):
            st.write("Removing invalid credentials")
            del st.session_state.gmail_credentials
    """Authenticates with Gmail API using appropriate flow based on environment."""
    # Debug info
    with st.expander("Gmail Authentication Debugging", expanded=False):
        st.write("Session state keys:", list(st.session_state.keys()))
        st.write("Query parameters:", st.query_params)
    
    # Check if we already have credentials
    if "gmail_credentials" in st.session_state:
        creds = st.session_state.gmail_credentials
        # Refresh token if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                st.session_state.gmail_credentials = creds
                logger.info("Gmail credentials refreshed successfully")
            except Exception as e:
                logger.error(f"Error refreshing Gmail credentials: {e}")
                del st.session_state.gmail_credentials
                st.rerun()
    else:
        # Load client config
        try:
            client_config = get_google_credentials()
            if not client_config:
                logger.error("Google API credentials not found")
                st.error("Gmail credentials not found. Check configuration.")
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
                    st.session_state.gmail_credentials = creds
                    st.success("Authentication completed! You can now use Gmail.")
                else:
                    # Deployed environment: use redirect URI approach
                    # Get the deployment URL
                    base_url = get_deployed_url()
                    redirect_uri = f"{base_url}"  # No trailing slash or path
                    
                    logger.info(f"Using redirect URI for Gmail: {redirect_uri}")
                    
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
                            st.session_state.gmail_credentials = flow.credentials
                            
                            # Clean up the URL
                            try:
                                st.set_query_params()
                            except:
                                pass
                                
                            st.success("Gmail authentication successful!")
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
                        st.warning("Authentication required for Gmail access.")
                        st.markdown(f"[Click here to authenticate with Gmail]({auth_url})")
                        return None
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Error removing temp file: {e}")
                
        except Exception as e:
            logger.error(f"Error in Gmail authentication setup: {e}")
            st.error(f"Error setting up Gmail authentication: {str(e)}")
            return None

    try:
        # Build and return Gmail service
        service = build('gmail', 'v1', credentials=st.session_state.gmail_credentials)
        logger.info("Gmail service created successfully")
        return service
        
    except Exception as e:
        logger.error(f"Error building Gmail service: {e}")
        st.error(f"Error connecting to Gmail: {str(e)}")
        if "gmail_credentials" in st.session_state:
            del st.session_state.gmail_credentials
        return None

def fetch_recent_emails(service: Any, total_emails: int = 50, query: str = "") -> List[Dict[str, Any]]:
    """
    Fetches recent emails from Gmail inbox.
    
    Args:
        service: Gmail API service object
        total_emails: Maximum number of emails to fetch
        query: Gmail search query string (e.g. "from:example@gmail.com")
        
    Returns:
        List of email details including id, subject, sender, and snippet
    """
    if not service:
        logger.error("Gmail service not initialized")
        return []
    
    emails = []
    next_page_token = None
    
    try:
        logger.info(f"Fetching up to {total_emails} emails" + (f" with query: {query}" if query else ""))
        
        # Fetch email IDs first
        while len(emails) < total_emails:
            params = {
                "userId": "me", 
                "maxResults": min(50, total_emails - len(emails))
            }
            
            if query:
                params["q"] = query
                
            if next_page_token:
                params["pageToken"] = next_page_token
                
            result = service.users().messages().list(**params).execute()
            messages = result.get("messages", [])
            
            if not messages:
                logger.info("No more messages found")
                break
                
            emails.extend(messages)
            next_page_token = result.get("nextPageToken")
            
            if not next_page_token:
                logger.info("No next page token, reached end of results")
                break
        
        logger.info(f"Found {len(emails)} email IDs")
        
        # Now retrieve full details for each email
        detailed_emails = []
        for i, msg in enumerate(emails):
            try:
                msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
                
                # Extract email details
                snippet = msg_data.get("snippet", "")
                headers = msg_data["payload"].get("headers", [])
                
                # Extract subject and sender from headers
                subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), None)
                sender = next((h["value"] for h in headers if h["name"].lower() == "from"), None)
                date = next((h["value"] for h in headers if h["name"].lower() == "date"), None)
                
                # Extract message body (simple extraction, may need enhancement for complex emails)
                body = ""
                if "parts" in msg_data["payload"]:
                    for part in msg_data["payload"]["parts"]:
                        if part["mimeType"] == "text/plain":
                            body_data = part["body"].get("data", "")
                            if body_data:
                                body = base64.urlsafe_b64decode(body_data).decode("utf-8")
                                break
                elif "body" in msg_data["payload"] and "data" in msg_data["payload"]["body"]:
                    body_data = msg_data["payload"]["body"]["data"]
                    body = base64.urlsafe_b64decode(body_data).decode("utf-8")
                
                detailed_emails.append({
                    "id": msg["id"],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "snippet": snippet,
                    "body": body
                })
                
                # Log progress for long operations
                if (i+1) % 10 == 0:
                    logger.info(f"Processed {i+1}/{len(emails)} emails")
                
            except Exception as e:
                logger.error(f"Error fetching details for email {msg['id']}: {e}")
                # Continue with next email
        
        logger.info(f"Successfully fetched details for {len(detailed_emails)} emails")
        return detailed_emails
        
    except HttpError as error:
        logger.error(f"HTTP error fetching emails: {error}", exc_info=True)
        st.error(f"Error fetching emails: {str(error)}")
        return []
    except Exception as e:
        logger.error(f"Error fetching emails: {e}", exc_info=True)
        st.error(f"Error fetching emails: {str(e)}")
        return []

def send_email(service: Any, to: str, subject: str, body: str, 
               cc: Optional[str] = None, bcc: Optional[str] = None, 
               attachment_path: Optional[str] = None) -> bool:
    """
    Sends an email using Gmail API.
    
    Args:
        service: Gmail API service object
        to: Recipient email address
        subject: Email subject
        body: Email body text
        cc: Carbon copy recipients (optional)
        bcc: Blind carbon copy recipients (optional)
        attachment_path: Path to file to attach (optional)
        
    Returns:
        True if successful, False otherwise
    """
    if not service:
        logger.error("Gmail service not initialized")
        return False
    
    try:
        # Create message
        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject
        
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
            
        # Add body
        message.attach(MIMEText(body))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            content_type, encoding = 'application/octet-stream', None
            main_type, sub_type = content_type.split('/', 1)
            
            with open(attachment_path, 'rb') as file:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(file.read())
                
            encoders.encode_base64(attachment)
            filename = os.path.basename(attachment_path)
            attachment.add_header('Content-Disposition', f'attachment; filename={filename}')
            message.attach(attachment)
            
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send message
        message = service.users().messages().send(
            userId="me", 
            body={'raw': raw_message}
        ).execute()
        
        logger.info(f"Email sent successfully (Message ID: {message['id']})")
        return True
        
    except HttpError as error:
        logger.error(f"HTTP error sending email: {error}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return False

def get_email_labels(service: Any) -> List[str]:
    """
    Fetches all available Gmail labels.
    
    Args:
        service: Gmail API service object
        
    Returns:
        List of label names
    """
    if not service:
        logger.error("Gmail service not initialized")
        return []
    
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        label_names = [label['name'] for label in labels]
        logger.info(f"Retrieved {len(label_names)} labels")
        return label_names
        
    except Exception as e:
        logger.error(f"Error fetching labels: {e}", exc_info=True)
        return []

def search_emails(service: Any, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Searches for emails matching the query.
    
    Args:
        service: Gmail API service object
        query: Gmail search query (e.g. "from:someone@example.com after:2023/01/01")
        max_results: Maximum number of results to return
        
    Returns:
        List of email details
    """
    return fetch_recent_emails(service, total_emails=max_results, query=query)

def mark_email_read(service: Any, msg_id: str) -> bool:
    """
    Marks an email as read.
    
    Args:
        service: Gmail API service object
        msg_id: Email message ID
        
    Returns:
        True if successful, False otherwise
    """
    if not service:
        logger.error("Gmail service not initialized")
        return False
    
    try:
        service.users().messages().modify(
            userId='me', 
            id=msg_id, 
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        logger.info(f"Marked email {msg_id} as read")
        return True
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}", exc_info=True)
        return False

def extract_email_threads(emails: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups emails by thread.
    
    Args:
        emails: List of email details
        
    Returns:
        Dictionary mapping thread IDs to lists of emails
    """
    threads = {}
    
    for email in emails:
        thread_id = email.get("threadId", "")
        if thread_id:
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(email)
    
    # Sort emails within each thread by date
    for thread_id in threads:
        threads[thread_id].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    return threads
import os
import pickle
import base64
import logging
import json
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
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
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
    """
    Authenticates with Gmail API and returns a service object.
    Uses session state instead of token files for Streamlit Cloud.
    """
    try:
        # Try to get credentials from session state
        creds = st.session_state.get("gmail_credentials", None)
        
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
                    st.error("Gmail credentials not found. Check configuration.")
                    return None
                
                # Create flow
                flow = get_streamlit_oauth_flow(credentials_dict, SCOPES)
                if not flow:
                    st.error("Failed to create authentication flow")
                    return None
                
                # Generate the authorization URL
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                # Display instructions to the user
                st.info("Authentication required for Gmail access.")
                st.markdown(f"1. Click this link to authorize: [Authorize Gmail Access]({auth_url})")
                st.markdown("2. Sign in and grant permission")
                st.markdown("3. After authentication, you'll be redirected back to the app")
                st.markdown("4. If you're not redirected automatically, copy the authorization code from the URL")
                
                # Get the authorization code from the user
                auth_code = st.text_input("If not redirected, enter the authorization code:", key="gmail_auth_code")
                
                if not auth_code:
                    return None
                    
                # Exchange the authorization code for credentials
                try:
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    st.success("Gmail authentication successful!")
                except Exception as e:
                    st.error(f"Authentication error: {e}")
                    return None
            
            # Save credentials to session state
            st.session_state["gmail_credentials"] = creds
        
        # Build and return Gmail service
        service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail service created successfully")
        return service
        
    except Exception as e:
        logger.error(f"Error creating Gmail service: {e}", exc_info=True)
        st.error(f"Error connecting to Gmail: {str(e)}")
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
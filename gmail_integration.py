import base64
import logging
from typing import List, Dict, Optional, Any
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gmail_integration.log'
)
logger = logging.getLogger(__name__)

def get_gmail_service():
    """Get an authenticated Gmail service"""
    from google_auth import get_google_service
    return get_google_service('gmail')

def fetch_recent_emails(service, total_emails=50, query=""):
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
        return []
    except Exception as e:
        logger.error(f"Error fetching emails: {e}", exc_info=True)
        return []

# Keep all other existing functions like send_email, get_email_labels, search_emails, etc.
def send_email(service, to, subject, body, cc=None, bcc=None, attachment_path=None):
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

def extract_email_threads(emails):
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
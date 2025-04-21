# token_storage.py
import json
import logging
import streamlit as st
from cryptography.fernet import Fernet
import base64
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='token_storage.log'
)
logger = logging.getLogger(__name__)

# Function to get a secret from Streamlit secrets
def get_secret(key, default=None):
    """Simple version that doesn't import config.py"""
    if key in st.secrets:
        return st.secrets[key]
    # Handle nested keys like "google.drive_parent_folder_id"
    parts = key.split('.')
    if len(parts) > 1:
        current = st.secrets
        for part in parts:
            if part in current:
                current = current[part]
            else:
                return default
        return current
    return default

# Initialize Supabase client
def get_supabase_client():
    try:
        from supabase import create_client
        url = get_secret("supabase.url")
        key = get_secret("supabase.key")
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return None

# Get encryption key from secrets or generate a valid one
def get_encryption_key():
    key = get_secret("ENCRYPTION_KEY", None)
    if key:
        # Use the key from secrets
        return key.encode()
    else:
        # Generate a valid key if not provided
        try:
            return base64.urlsafe_b64encode(os.urandom(32))
        except Exception as e:
            logger.error(f"Error generating encryption key: {e}")
            # Provide a valid fallback key (NOT FOR PRODUCTION)
            return b'lzNiipUzCgW4sESOHWaBmE5w8ACMb7DBIP3U0wpzCuQ='

# Initialize Fernet with a valid key
ENCRYPTION_KEY = get_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_token(token_data):
    """Encrypt token data before storing in database"""
    if not token_data:
        return None
    token_json = json.dumps(token_data)
    encrypted_data = cipher_suite.encrypt(token_json.encode())
    return encrypted_data.decode()

def decrypt_token(encrypted_token):
    """Decrypt token data retrieved from database"""
    if not encrypted_token:
        return None
    try:
        decrypted_data = cipher_suite.decrypt(encrypted_token.encode())
        return json.loads(decrypted_data)
    except Exception as e:
        logger.error(f"Error decrypting token: {e}")
        return None

# Add this to your save_user_token function
def save_user_token(username, service, token_data):
    """Save a user's OAuth token to Supabase"""
    try:
        logger.info(f"Starting save_user_token for username={username}, service={service}")
        
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Failed to initialize Supabase client")
            return False
            
        logger.info("Supabase client initialized successfully")
        
        encrypted_token = encrypt_token(token_data)
        if not encrypted_token:
            logger.error("Failed to encrypt token data")
            return False
            
        logger.info("Token encrypted successfully")
        
        # Check if token already exists
        try:
            response = supabase.table("oauth_tokens").select("*").eq("username", username).eq("service", service).execute()
            logger.info(f"Query result: {response.data}")
        except Exception as e:
            logger.error(f"Error checking for existing token: {e}")
            return False
            
        try:
            if response.data:
                # Update existing record
                logger.info(f"Updating existing token for {username}/{service}")
                result = supabase.table("oauth_tokens").update({"token": encrypted_token}).eq("username", username).eq("service", service).execute()
                logger.info(f"Update result: {result}")
            else:
                # Insert new record
                logger.info(f"Inserting new token for {username}/{service}")
                result = supabase.table("oauth_tokens").insert({
                    "username": username,
                    "service": service,
                    "token": encrypted_token
                }).execute()
                logger.info(f"Insert result: {result}")
            
            logger.info(f"Saved {service} token for user {username}")
            return True
        except Exception as e:
            logger.error(f"Error saving to database: {e}", exc_info=True)
            return False
    except Exception as e:
        logger.error(f"Error in save_user_token: {e}", exc_info=True)
        return False

def get_user_token(username, service):
    """Retrieve a user's OAuth token from Supabase"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Failed to initialize Supabase client")
            return None
            
        response = supabase.table("oauth_tokens").select("token").eq("username", username).eq("service", service).execute()
        
        if response.data:
            encrypted_token = response.data[0]["token"]
            return decrypt_token(encrypted_token)
        return None
    except Exception as e:
        logger.error(f"Error retrieving token from Supabase: {e}")
        return None
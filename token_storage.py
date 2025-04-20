# token_storage.py (new file)
import json
import logging
import streamlit as st
from supabase import create_client
from config import get_secret
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='token_storage.log'
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
def get_supabase_client():
    url = get_secret("supabase.url")
    key = get_secret("supabase.key")
    return create_client(url, key)

# Encryption key (should be stored securely)
ENCRYPTION_KEY = get_secret("ENCRYPTION_KEY", "YOUR_DEFAULT_ENCRYPTION_KEY_HERE").encode()
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

def save_user_token(username, service, token_data):
    """Save a user's OAuth token to Supabase"""
    try:
        supabase = get_supabase_client()
        
        # Check if token already exists
        response = supabase.table("oauth_tokens").select("*").eq("username", username).eq("service", service).execute()
        
        encrypted_token = encrypt_token(token_data)
        if not encrypted_token:
            logger.error("Failed to encrypt token data")
            return False
            
        if response.data:
            # Update existing record
            supabase.table("oauth_tokens").update({"token": encrypted_token}).eq("username", username).eq("service", service).execute()
        else:
            # Insert new record
            supabase.table("oauth_tokens").insert({
                "username": username,
                "service": service,
                "token": encrypted_token
            }).execute()
        
        logger.info(f"Saved {service} token for user {username}")
        return True
    except Exception as e:
        logger.error(f"Error saving token to Supabase: {e}")
        return False

def get_user_token(username, service):
    """Retrieve a user's OAuth token from Supabase"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("oauth_tokens").select("token").eq("username", username).eq("service", service).execute()
        
        if response.data:
            encrypted_token = response.data[0]["token"]
            return decrypt_token(encrypted_token)
        return None
    except Exception as e:
        logger.error(f"Error retrieving token from Supabase: {e}")
        return None

def delete_user_token(username, service):
    """Delete a user's OAuth token from Supabase"""
    try:
        supabase = get_supabase_client()
        supabase.table("oauth_tokens").delete().eq("username", username).eq("service", service).execute()
        logger.info(f"Deleted {service} token for user {username}")
        return True
    except Exception as e:
        logger.error(f"Error deleting token from Supabase: {e}")
        return False
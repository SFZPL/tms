# token_storage.py
import json
import logging
import streamlit as st
from cryptography.fernet import Fernet
import base64
import os
import time
import traceback

# Configure logging with more details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='token_storage.log'
)
logger = logging.getLogger(__name__)

# Add console handler for easier debugging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

def get_secret(key, default=None):
    """Improved secret access with debug output"""
    print(f"Attempting to access secret: {key}")
    
    # Direct access first
    if key in st.secrets:
        print(f"Found secret '{key}' via direct access")
        return st.secrets[key]
    
    # Check for nested keys
    parts = key.split('.')
    if len(parts) > 1:
        current = st.secrets
        for part in parts:
            if part in current:
                current = current[part]
            else:
                print(f"Nested key part '{part}' not found in '{key}'")
                return default
        print(f"Found secret '{key}' via nested access")
        return current
        
    # Debug output of available keys (not showing values for security)
    available_keys = list(st.secrets.keys())
    print(f"Available top-level secret keys: {available_keys}")
    
    print(f"Secret key '{key}' not found in available keys")
    return default
# In token_storage.py, modify get_supabase_client to return just the client:
def get_supabase_client():
    try:
        try:
            from supabase import create_client
        except ImportError:
            logger.error("supabase-py package not installed")
            return None
            
        url = get_secret("supabase.url")
        key = get_secret("supabase.key")
        
        if not url or not key:
            logger.error(f"Missing Supabase credentials")
            return None
            
        client = create_client(url, key)
        return client  # Return just the client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return None
def get_encryption_key():
    """Get or generate encryption key with improved security"""
    key = get_secret("ENCRYPTION_KEY", None)
    if key:
        try:
            # Ensure key is properly formatted for Fernet
            if isinstance(key, str):
                if len(key) < 32:  # Minimum entropy needed
                    logger.warning("Provided encryption key is too short, generating new one")
                    return base64.urlsafe_b64encode(os.urandom(32))
                    
                # Try to decode the key to see if it's valid base64
                try:
                    base64.urlsafe_b64decode(key.encode())
                    return key.encode()
                except:
                    # If not valid base64, encode it properly
                    return base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0'))
            else:
                # Already bytes
                return base64.urlsafe_b64encode(key[:32].ljust(32, b'\0'))
        except Exception as e:
            logger.error(f"Error processing encryption key: {e}")
            
    # Generate a new key
    try:
        return base64.urlsafe_b64encode(os.urandom(32))
    except Exception as e:
        logger.error(f"Error generating encryption key: {e}")
        # Only use fallback in extreme cases
        return b'lzNiipUzCgW4sESOHWaBmE5w8ACMb7DBIP3U0wpzCuQ='

# Initialize encryption with better error handling
try:
    ENCRYPTION_KEY = get_encryption_key()
    cipher_suite = Fernet(ENCRYPTION_KEY)
    logger.info("Encryption initialized successfully")
except Exception as e:
    logger.error(f"Error initializing encryption: {e}")
    # Create a fallback that will at least not crash but log errors
    class FallbackFernet:
        def encrypt(self, data):
            logger.error("Using fallback encryption (NOT SECURE)")
            return base64.b64encode(data)
        def decrypt(self, data):
            logger.error("Using fallback decryption (NOT SECURE)")
            return base64.b64decode(data)
    cipher_suite = FallbackFernet()

def encrypt_token(token_data):
    """Encrypt token data with better error handling"""
    if not token_data:
        logger.warning("No token data to encrypt")
        return None
    try:
        token_json = json.dumps(token_data)
        encrypted_data = cipher_suite.encrypt(token_json.encode())
        return encrypted_data.decode()
    except Exception as e:
        logger.error(f"Error encrypting token: {e}")
        return None

def decrypt_token(encrypted_token):
    """Decrypt token data with better error handling"""
    if not encrypted_token:
        logger.warning("No encrypted token to decrypt")
        return None
    try:
        decrypted_data = cipher_suite.decrypt(encrypted_token.encode())
        return json.loads(decrypted_data)
    except Exception as e:
        logger.error(f"Error decrypting token: {e}")
        return None

def save_user_token(username, service, token_data):
    """Save a user's OAuth token with comprehensive error handling"""
    try:
        logger.info(f"Starting save_user_token for username={username}, service={service}")
        
        if not username or not service:
            logger.error(f"Invalid parameters: username={username}, service={service}")
            return False
            
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
            
            if hasattr(response, 'error') and response.error:
                logger.error(f"Query error: {response.error.message}")
                return False
                
            logger.info(f"Query result: Found {len(response.data)} existing records")
            
            if response.data:
                # Update existing record
                logger.info(f"Updating existing token for {username}/{service}")
                result = supabase.table("oauth_tokens").update({"token": encrypted_token}).eq("username", username).eq("service", service).execute()
                
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Update error: {result.error.message}")
                    return False
                    
                logger.info(f"Update successful: {len(result.data)} records affected")
            else:
                # Insert new record
                logger.info(f"Inserting new token for {username}/{service}")
                result = supabase.table("oauth_tokens").insert({
                    "username": username,
                    "service": service,
                    "token": encrypted_token
                }).execute()
                
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Insert error: {result.error.message}")
                    return False
                    
                logger.info(f"Insert successful: {len(result.data)} records created")
            
            logger.info(f"Saved {service} token for user {username}")
            return True
        except Exception as e:
            logger.error(f"Error in Supabase operation: {e}")
            logger.error(traceback.format_exc())
            return False
    except Exception as e:
        logger.error(f"Error in save_user_token: {e}")
        logger.error(traceback.format_exc())
        return False

def get_user_token(username, service):
    """Retrieve a user's OAuth token with better error handling"""
    try:
        logger.info(f"Getting token for username={username}, service={service}")
        
        if not username or not service:
            logger.error(f"Invalid parameters: username={username}, service={service}")
            return None
            
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Failed to initialize Supabase client")
            return False
            
        response = supabase.table("oauth_tokens").select("token").eq("username", username).eq("service", service).execute()
        
        if hasattr(response, 'error') and response.error:
            logger.error(f"Query error: {response.error.message}")
            return None
            
        logger.info(f"Query result: Found {len(response.data)} records")
        
        if response.data:
            encrypted_token = response.data[0]["token"]
            token_data = decrypt_token(encrypted_token)
            if token_data:
                logger.info(f"Successfully retrieved and decrypted token")
                return token_data
            else:
                logger.error("Failed to decrypt token")
                return None
        else:
            logger.info(f"No token found for {username}/{service}")
            return None
    except Exception as e:
        logger.error(f"Error in get_user_token: {e}")
        logger.error(traceback.format_exc())
        return None

def test_supabase_connection():
    """Test if Supabase connection is working"""
    try:
        logger.info("Testing Supabase connection...")
        
        # Get Supabase client
        supabase = get_supabase_client()
        if not supabase:
            logger.error("Failed to initialize Supabase client")
            return False
        # Try to access the oauth_tokens table
        try:
            # First try a simple query that doesn't modify data
            response = supabase.table("oauth_tokens").select("count").limit(1).execute()
            
            if hasattr(response, 'error') and response.error:
                return False, f"Table query failed: {response.error.message}"
                
            logger.info("Read access to oauth_tokens table confirmed")
            
            # Now try a write operation with a test record
            test_id = f"test_{int(time.time())}"
            
            # Test encryption
            test_token = encrypt_token({"test": "data"})
            if not test_token:
                return False, "Encryption test failed"
                
            logger.info("Encryption test passed")
            
            # Insert test record
            insert_result = supabase.table("oauth_tokens").insert({
                "username": test_id,
                "service": "test_service",
                "token": test_token
            }).execute()
            
            if hasattr(insert_result, 'error') and insert_result.error:
                return False, f"Insert test failed: {insert_result.error.message}"
                
            logger.info("Insert test passed")
            
            # Clean up the test record
            delete_result = supabase.table("oauth_tokens").delete().eq("username", test_id).execute()
            
            if hasattr(delete_result, 'error') and delete_result.error:
                logger.warning(f"Cleanup failed: {delete_result.error.message}")
            else:
                logger.info("Cleanup successful")
                
            return True, "Connection test successful! Read, write, and encryption all working."
            
        except Exception as e:
            logger.error(f"Table operation error: {e}")
            logger.error(traceback.format_exc())
            return False, f"Table operation error: {str(e)}"
            
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        logger.error(traceback.format_exc())
        return False, f"Connection test failed with error: {str(e)}"
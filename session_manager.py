import streamlit as st
from datetime import datetime, timedelta
import uuid
import logging
import sqlite3
import pickle
import base64
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='session_manager.log'
)
logger = logging.getLogger(__name__)

class SessionManager:
    """Centralized manager for application session state"""
    
    # Session keys by category
    AUTH_KEYS = ['logged_in', 'login_time', 'session_expiry', 'user']
    ODOO_KEYS = ['odoo_uid', 'odoo_models', 'odoo_connection']
    GOOGLE_KEYS = ['google_gmail_creds', 'google_drive_creds']
    FLOW_KEYS = ['form_type', 'company_selection_done', 'adhoc_sales_order_done', 
                'adhoc_parent_input_done', 'retainer_parent_input_done', 
                'subtask_index', 'created_tasks', 'designer_selection',
                'email_analysis_done', 'email_analysis_skipped']
    DATA_KEYS = ['sales_orders', 'companies', 'adhoc_subtasks', 'email_analysis',
                'recent_emails', 'email_threads', 'drive_folder_id', 'drive_folder_link']
    
    @staticmethod
    def initialize_session():
        """Initialize new session if none exists"""
        if 'initialized' not in st.session_state:
            logger.info("Initializing new session state")
            st.session_state.initialized = True
            st.session_state.last_activity = datetime.now()
            
            # Initialize authentication state
            for key in SessionManager.AUTH_KEYS:
                if key not in st.session_state:
                    st.session_state[key] = None
            
            # CRITICAL FIX: Always set user to empty dict if None
            if st.session_state.user is None:
                st.session_state.user = {}
            
            # Set default values
            st.session_state.debug_mode = None
    @staticmethod
    def check_session_expiry(expiry_hours=8):
        """
        Check if the current session has expired
        
        Args:
            expiry_hours: Number of hours before session expires
            
        Returns:
            True if valid, False if expired
        """
        # Initialize if needed
        SessionManager.initialize_session()
        
        # Update last activity time
        st.session_state.last_activity = datetime.now()
        
        # Check for login and expiry
        if not st.session_state.get("logged_in", False):
            return False
            
        if "login_time" not in st.session_state:
            st.session_state.login_time = datetime.now()
            st.session_state.session_expiry = datetime.now() + timedelta(hours=expiry_hours)
            
        # Check expiry
        if datetime.now() > st.session_state.session_expiry:
            logger.info("Session expired")
            SessionManager.logout(expired=True)
            return False
            
        return True
    
    @staticmethod
    def login(username: str, expiry_hours: int = 8):
        """
        Log in a user and set up session
        
        Args:
            username: Username to log in
            expiry_hours: Hours until session expires
        """
        # Set login state
        login_time = datetime.now()
        session_expiry = login_time + timedelta(hours=expiry_hours)
        
        st.session_state.logged_in = True
        st.session_state.login_time = login_time
        st.session_state.session_expiry = session_expiry
        st.session_state.user = {
            "username": username,
            "session_id": str(uuid.uuid4())
        }
        
        # IMPORTANT: Restore Google credentials if previously saved
        if "_persistent_google_creds" in st.session_state:
            saved_creds = st.session_state._persistent_google_creds
            if saved_creds:
                # Restore all Google credentials
                st.session_state.google_gmail_creds = saved_creds.get("gmail_creds")
                st.session_state.google_drive_creds = saved_creds.get("drive_creds") 
                st.session_state.gmail_auth_complete = saved_creds.get("gmail_auth_complete", False)
                st.session_state.drive_auth_complete = saved_creds.get("drive_auth_complete", False)
                st.session_state.google_auth_complete = saved_creds.get("google_auth_complete", False)
        
        logger.info(f"User {username} logged in. Session expires at {session_expiry}")
    
    @staticmethod
    def logout(expired: bool = False):
        """
        Log out user and clear session state
        
        Args:
            expired: Whether logout is due to session expiry
        """
        # Log the logout
        if st.session_state.get("logged_in") and st.session_state.get("user"):
            username = st.session_state.user.get("username", "Unknown")
            logger.info(f"User {username} logged out. Expired: {expired}")
        
        # IMPORTANT: Save Google credentials before clearing session
        google_creds = {
            "gmail_creds": st.session_state.get("google_gmail_creds"),
            "drive_creds": st.session_state.get("google_drive_creds"),
            "gmail_auth_complete": st.session_state.get("gmail_auth_complete", False),
            "drive_auth_complete": st.session_state.get("drive_auth_complete", False),
            "google_auth_complete": st.session_state.get("google_auth_complete", False)
        }
        
        # Persist credentials in Streamlit's browser-based storage
        if google_creds["gmail_creds"]:
            st.session_state["_persistent_google_creds"] = google_creds
        
        # Clear most state but keep debug and persistence
        debug_mode = st.session_state.get("debug_mode")
        persistent_creds = st.session_state.get("_persistent_google_creds")
        
        # Clear state
        for key in list(st.session_state.keys()):
            if key not in ["debug_mode", "_persistent_google_creds"]:
                st.session_state.pop(key, None)
        
        # Restore persistent values
        if debug_mode:
            st.session_state.debug_mode = debug_mode
        if persistent_creds:
            st.session_state._persistent_google_creds = persistent_creds
        
        # Re-initialize session
        SessionManager.initialize_session()
        
        # Show expiry message if needed
        if expired:
            st.warning("Your session has expired. Please log in again.")
        
    @staticmethod
    def clear_flow_data():
        """Clear all flow-related data but keep authentication"""
        flow_keys = SessionManager.FLOW_KEYS + SessionManager.DATA_KEYS + [
            'parent_task_id',  # Add this to ensure it's cleared properly
            'adhoc_parent_task_title', 'adhoc_target_language', 'adhoc_guidelines',
            'adhoc_client_success_exec', 'adhoc_request_receipt_dt',
            'adhoc_client_due_date_parent', 'adhoc_internal_due_date',
            'adhoc_parent_description', 'adhoc_subtasks',
            'retainer_project', 'retainer_parent_task_title', 'retainer_customer',
            'retainer_target_language', 'retainer_guidelines',
            'retainer_client_success_exec', 'retainer_request_receipt_dt',
            'retainer_internal_dt', 'drive_folder_id', 'drive_folder_link',
            'google_auth_complete'
        ]
        for key in flow_keys:
            if key in st.session_state:
                st.session_state.pop(key, None)
    
    @staticmethod
    def get_session_info() -> Dict[str, Any]:
        """Get information about current session"""
        info = {
            "logged_in": st.session_state.get("logged_in", False),
            "username": st.session_state.get("user", {}).get("username", "Not logged in"),
            "session_id": st.session_state.get("user", {}).get("session_id", None),
        }
        
        if st.session_state.get("logged_in"):
            info.update({
                "login_time": st.session_state.get("login_time", None),
                "expiry_time": st.session_state.get("session_expiry", None),
                "time_remaining": (
                    st.session_state.get("session_expiry", datetime.now()) - datetime.now()
                ).total_seconds() / 3600 if st.session_state.get("session_expiry") else 0
            })
            
        return info
    
    @staticmethod
    def reset_to_homepage():
        """Reset the application flow to the homepage"""
        flow_keys = SessionManager.FLOW_KEYS + ['email_analysis', 'selected_company']
        for key in flow_keys:
            st.session_state.pop(key, None)

    @staticmethod
    def handle_error(error, context="Operation"):
        """
        Handle errors gracefully with appropriate actions
        
        Args:
            error: The exception/error
            context: Context where the error occurred
        """
        logger.error(f"Error in {context}: {error}", exc_info=True)
        
        # Check for authentication errors
        if "authentication" in str(error).lower() or "credentials" in str(error).lower():
            st.error(f"Authentication error: {error}")
            
            # Clear related credentials
            if "odoo" in context.lower():
                for key in SessionManager.ODOO_KEYS:
                    st.session_state.pop(key, None)
            
            if "google" in context.lower() or "gmail" in context.lower() or "drive" in context.lower():
                for key in SessionManager.GOOGLE_KEYS:
                    st.session_state.pop(key, None)
                    
            return False
        
        # General error handling
        st.error(f"Error in {context}: {error}")
        return False

    @staticmethod
    def reset_flow_state(flow_name):
        """
        Reset the flow state for a specific flow
        
        Args:
            flow_name: Name of the flow ('adhoc' or 'retainer')
        """
        if flow_name == 'adhoc':
            keys_to_remove = [
                'adhoc_sales_order_done', 'adhoc_parent_input_done', 
                'subtask_index', 'adhoc_subtasks',
                'parent_sales_order_item', 'customer', 'project'
            ]
        elif flow_name == 'retainer':
            keys_to_remove = [
                'retainer_parent_input_done', 'retainer_project',
                'retainer_parent_task_title', 'retainer_customer'
            ]
        else:
            return
        
        for key in keys_to_remove:
            st.session_state.pop(key, None)
    @staticmethod
    def update_activity():
        """Update the last activity timestamp"""
        st.session_state.last_activity = datetime.now()

    @staticmethod
    def check_inactivity(max_idle_minutes=30):
        """
        Check if the session has been inactive too long
        
        Args:
            max_idle_minutes: Maximum idle time in minutes
            
        Returns:
            True if active, False if inactive too long
        """
        if "last_activity" not in st.session_state:
            st.session_state.last_activity = datetime.now()
            return True
        
        idle_time = datetime.now() - st.session_state.last_activity
        if idle_time.total_seconds() > (max_idle_minutes * 60):
            logger.info(f"Session inactive for {idle_time.total_seconds()/60:.1f} minutes")
            SessionManager.logout(expired=True)
            return False
        
        return True
    
    @staticmethod
    def get_user_by_email(email):
        """Get user data from database by email"""
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("SELECT email, odoo_user_id, google_tokens FROM users WHERE email = ?", (email,))
        user_data = c.fetchone()
        conn.close()
        return user_data

    @staticmethod
    def save_google_tokens(email, tokens):
        """Save encrypted Google tokens to database"""
        if not email or not tokens:
            return False
            
        # Serialize and encrypt tokens
        serialized = pickle.dumps(tokens)
        encrypted = cipher.encrypt(serialized)
        encoded = base64.b64encode(encrypted).decode()
        
        # Save to database
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute('''
        INSERT OR REPLACE INTO users (email, google_tokens, last_login) 
        VALUES (?, ?, datetime('now'))
        ''', (email, encoded))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def load_google_tokens(email):
        """Load and decrypt Google tokens from database"""
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("SELECT google_tokens FROM users WHERE email = ?", (email,))
        result = c.fetchone()
        conn.close()
        
        if not result or not result[0]:
            return None
            
        try:
            # Decrypt and deserialize
            encoded = result[0]
            encrypted = base64.b64decode(encoded)
            decrypted = cipher.decrypt(encrypted)
            tokens = pickle.loads(decrypted)
            return tokens
        except Exception as e:
            logger.error(f"Error decrypting tokens: {e}")
            return None
        
# Add to session_manager.py

@staticmethod
def get_user_by_email(email):
    """Get user data from database by email"""
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT email, odoo_user_id, google_tokens FROM users WHERE email = ?", (email,))
    user_data = c.fetchone()
    conn.close()
    return user_data

@staticmethod
def save_google_tokens(email, tokens):
    """Save encrypted Google tokens to database"""
    if not email or not tokens:
        return False
        
    # Import dependencies here to avoid circular imports
    from app import cipher
    
    # Serialize and encrypt tokens
    serialized = pickle.dumps(tokens)
    encrypted = cipher.encrypt(serialized)
    encoded = base64.b64encode(encrypted).decode()
    
    # Save to database
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
    INSERT OR REPLACE INTO users (email, google_tokens, last_login) 
    VALUES (?, ?, datetime('now'))
    ''', (email, encoded))
    conn.commit()
    conn.close()
    return True

@staticmethod
def load_google_tokens(email):
    """Load and decrypt Google tokens from database"""
    # Import dependencies here to avoid circular imports
    from app import cipher
    
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute("SELECT google_tokens FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return None
        
    try:
        # Decrypt and deserialize
        encoded = result[0]
        encrypted = base64.b64decode(encoded)
        decrypted = cipher.decrypt(encrypted)
        tokens = pickle.loads(decrypted)
        return tokens
    except Exception as e:
        logger.error(f"Error decrypting tokens: {e}")
        return None
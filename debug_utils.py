import os
import streamlit as st
import logging
import traceback
import json
import platform
import sys
import functools

class SystemDebugger:
    def __init__(self):
        """
        Initialize comprehensive system debugging utilities
        """
        self.logger = logging.getLogger('system_debugger')
        self.logger.setLevel(logging.DEBUG)
        
        # Ensure log file exists and is writable
        log_file = 'system_debug.log'
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def capture_environment_info(self):
        """
        Capture comprehensive system and environment information
        """
        env_info = {
            "Python Version": sys.version,
            "Platform": platform.platform(),
            "System": platform.system(),
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "Python Executable": sys.executable,
            "Python Path": sys.path,
            "Environment Variables": dict(os.environ),
            "Streamlit Version": getattr(st, '__version__', 'Unknown'),
            "Session State Keys": list(st.session_state.keys()) if hasattr(st, 'session_state') else "No session state"
        }
        return env_info

    def log_exception(self, e, context=""):
        """
        Log detailed exception information
        """
        self.logger.error(f"Exception in {context}")
        self.logger.error(f"Exception Type: {type(e).__name__}")
        self.logger.error(f"Exception Message: {str(e)}")
        self.logger.error("Full Traceback:")
        self.logger.error(traceback.format_exc())

    def debug_oauth_configuration(self, service_name):
        """
        Debug OAuth configuration for a specific service
        """
        try:
            from config import get_google_credentials
            
            credentials = get_google_credentials()
            if not credentials:
                self.logger.error(f"No {service_name} credentials found")
                return False
            
            # Log credential details (be careful with sensitive information)
            safe_credentials = credentials.copy()
            if 'web' in safe_credentials:
                web_creds = safe_credentials['web']
                # Mask sensitive parts
                if 'client_secret' in web_creds:
                    web_creds['client_secret'] = web_creds['client_secret'][:5] + '...'
            
            self.logger.debug(f"{service_name} Credentials Configuration:")
            self.logger.debug(json.dumps(safe_credentials, indent=2))
            
            # Validate redirect URIs
            redirect_uris = credentials.get('web', {}).get('redirect_uris', [])
            self.logger.debug(f"Redirect URIs: {redirect_uris}")
            
            return True
        except Exception as e:
            self.log_exception(e, f"{service_name} OAuth Configuration")
            return False

    def streamlit_debug_page(self):
        """
        Create a Streamlit debug information page
        """
        st.title("🔍 System Debugging Dashboard")
        
        # Environment Information
        with st.expander("🖥️ System Environment"):
            env_info = self.capture_environment_info()
            for key, value in env_info.items():
                st.text(f"{key}: {str(value)[:500]}")  # Truncate long values
        
        # OAuth Configuration Debug
        with st.expander("🔐 OAuth Configuration"):
            st.subheader("Google OAuth Debug")
            google_debug = self.debug_oauth_configuration("Google")
            st.write("OAuth Configuration Status:", 
                     "✅ Configured" if google_debug else "❌ Configuration Issue")
        
        # Logs Viewer
        with st.expander("📄 Recent Logs"):
            try:
                with open('system_debug.log', 'r') as log_file:
                    logs = log_file.readlines()
                    st.text_area("Log Contents", 
                                 value='\n'.join(logs[-100:]), 
                                 height=300)
            except Exception as e:
                st.error(f"Could not read log file: {e}")
        
        # Additional Debugging Options
        st.subheader("Debug Actions")
        if st.button("Clear Session State"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Session state cleared!")
        
        if st.button("Reset OAuth Credentials"):
            # Implement a safe way to reset or clear OAuth credentials
            st.warning("OAuth credential reset functionality to be implemented")

def debug_function(func):
    """
    Decorator to add debugging to functions
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debugger = SystemDebugger()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            debugger.log_exception(e, f"Error in {func.__name__}")
            raise
    return wrapper

def inject_debug_page():
    """
    Inject a debug page into the Streamlit application
    """
    debugger = SystemDebugger()
    
    if st.session_state.get("debug_mode") == "system_debug":
        debugger.streamlit_debug_page()
        
        if st.button("Return to Normal Mode"):
            st.session_state.pop("debug_mode")
            st.rerun()
        return True
    return False

# Global exception handler
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Global exception handler for unhandled exceptions
    """
    try:
        logger = logging.getLogger('global_exception_handler')
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    except Exception:
        # Fallback logging in case of any issue
        print("Global exception handler failed")
        traceback.print_exception(exc_type, exc_value, exc_traceback)

# Set the global exception handler
sys.excepthook = global_exception_handler

# Export utilities
__all__ = ['SystemDebugger', 'debug_function', 'inject_debug_page']
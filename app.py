import os
import sys

# ─── Make sure local modules and the data folder are importable ─────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now try to import
import streamlit as st
# Set page config
st.set_page_config(
    page_title="Task Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    from config import get_secret
except ImportError as e:
    print(f"Error importing config: {e}")
    # Fallback implementation
    def get_secret(key, default=None):
        """Fallback get_secret implementation"""
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
        return os.environ.get(key, default)
    
# ─── Standard library ─────────────────────────────────────────────────────────
import logging
import traceback
import re
import uuid
from pathlib import Path
from datetime import datetime, date, time
from typing import Any, Dict, List, Optional, Tuple, Union

# ─── Third‑party ──────────────────────────────────────────────────────────────
import pandas as pd

# ─── Local modules ───────────────────────────────────────────────────────────
from config import get_secret

# Debug util (graceful fallback if missing)
try:
    from debug_utils import inject_debug_page, debug_function, SystemDebugger
except ImportError:
    def inject_debug_page(): return False
    def debug_function(f): return f
    class SystemDebugger:
        def streamlit_debug_page(self): pass

# Core helpers (all secrets now loaded inside these functions)
from helpers import (
    authenticate_odoo,
    create_odoo_task,
    get_sales_orders,
    get_sales_order_details,
    get_employee_schedule,
    create_task,
    find_employee_id,
    get_target_languages_odoo,
    get_guidelines_odoo,
    get_client_success_executives_odoo,
    get_service_category_1_options,
    get_service_category_2_options,
    get_all_employees_in_planning,
    find_earliest_available_slot,
    get_companies,
    get_retainer_projects,
    get_retainer_customers,
    get_project_id_by_name,
    update_task_designer,
    get_odoo_connection,
    check_odoo_connection,
    get_available_fields
)
from gmail_integration import get_gmail_service, fetch_recent_emails
from azure_llm import analyze_email
from designer_selector import (
    load_designers,
    suggest_best_designer,
    suggest_best_designer_available,
    filter_designers_by_availability,
    rank_designers_by_skill_match,
    suggest_reshuffling
)

from prezlab_ui import inject_custom_css, header, container, message, progress_steps, scribble, add_logo

# Add this line after your existing imports
from enhanced_prezlab_ui import (
    inject_enhanced_css,
    create_animated_header,
    create_notification,
    create_progress_steps,
    create_glass_card,
    create_task_card,
    style_form_container,
    create_metric_card,
    show_loading_animation,
    COLORS
)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)


# At the top of app.py, after imports
def get_odoo_credentials():
    """Get Odoo credentials from session state"""
    if 'odoo_credentials' in st.session_state:
        creds = st.session_state.odoo_credentials
        return creds.get('url'), creds.get('db'), creds.get('email'), creds.get('password')
    return None, None, None, None

# Update the constants
ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD = get_odoo_credentials()

def add_debug_sidebar(debugger: SystemDebugger):
    """
    Add a debug sidebar option to the existing sidebar
    """
    if st.session_state.user['username'] == 'admin':
        st.sidebar.markdown("---")
        st.sidebar.subheader("🐞 Debugging")
        if st.sidebar.button("System Debug Dashboard"):
            # Switch to debug mode
            st.session_state.debug_mode = "system_debug"

def handle_debug_mode(debugger: SystemDebugger):
    """
    Handle the system debug mode rendering
    """
    if st.session_state.get("debug_mode") == "system_debug":
        debugger.streamlit_debug_page()
        # Add a button to return to normal mode
        if st.button("Return to Normal Mode"):
            st.session_state.pop("debug_mode")
            st.rerun()
        return True
    return False

def setup_debugging(main_app):
    """
    Set up debugging for the main Streamlit application
    """
    # Inject debug handlers and get debugger instance
    debugger = inject_debug_page(main_app)
    
    # Modify the sidebar render function to add debug option
    original_render_sidebar = main_app.render_sidebar
    
    def modified_render_sidebar():
        original_render_sidebar()
        add_debug_sidebar(debugger)
    
    main_app.render_sidebar = modified_render_sidebar
    
    return debugger

def validate_session():
    """
    Validates the current session and handles expiry
    """
    from session_manager import SessionManager
    
    # CRITICAL FIX: Skip validation if OAuth flow is in progress
    if "code" in st.query_params:
        return True
    
    # Update activity timestamp
    SessionManager.update_activity()
    
    # Check if logged in
    if not st.session_state.get("logged_in", False):
        return False
    
    # Check if we have Odoo credentials
    if "odoo_credentials" not in st.session_state:
        return False
    
    # Check for session expiry
    if not SessionManager.check_session_expiry():
        return False
    
    # Validate Odoo connection
    if not check_odoo_connection():
        with st.spinner("Reconnecting to Odoo..."):
            uid, models = get_odoo_connection(force_refresh=True)
            if not uid or not models:
                create_notification("Lost connection to Odoo. Please log in again.", "error")
                SessionManager.logout()
                return False
    
    return True
# # Add a more comprehensive OpenAI debug in the auth_debug_page function:
# def add_openai_debug_section():
#     """Add this to your auth_debug_page() function"""
    
#     st.subheader("OpenAI API Testing")
    
#     col1, col2 = st.columns(2)
    
#     with col1:
#         st.write("**Configuration Status:**")
        
#         # Check API key
#         from config import get_secret
#         api_key = get_secret("OPENAI_API_KEY")
#         if api_key:
#             create_notification(f"✅ API Key configured ({len(api_key)} chars)", "success")
#             st.text(f"Key preview: {api_key[:15]}...{api_key[-4:]}")
#         else:
#             create_notification("❌ No API key found", "error")
            
#         # Check model setting
#         model = get_secret("OPENAI_MODEL", "gpt-4")
#         create_notification(f"Default model: {model}", "info")
        
#         # Check OpenAI version
#         try:
#             import openai
#             if hasattr(openai, '__version__'):
#                 create_notification(f"OpenAI library version: {openai.__version__}", "info")
#             else:
#                 create_notification("Cannot determine OpenAI version", "warning")
#         except ImportError:
#             create_notification("OpenAI library not installed", "error")
    
#     with col2:
#         st.write("**API Tests:**")
        
#         # Simple API test
#         if st.button("Test Simple API Call", key="test_openai_simple"):
#             test_openai_simple()
            
#         # Test designer matching
#         if st.button("Test Designer Matching", key="test_designer_ai"):
#             test_designer_matching()
            
#         # Test with different models
#         model_test = st.selectbox(
#             "Test with model:",
#             ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
#             key="model_test_select"
#         )
        
#         if st.button("Test Selected Model", key="test_selected_model"):
#             test_model(model_test)

def test_openai_simple():
    """Simple OpenAI API test - Updated for v1.0+"""
    try:
        from openai import OpenAI
        from config import get_secret
        
        api_key = get_secret("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        
        with st.spinner("Testing API..."):
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say 'Hello from OpenAI!'"}],
                max_tokens=20
            )
            
            create_notification(f"Response: {response.choices[0].message.content}", "success")
            st.json({
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else {}
            })
    except Exception as e:
        create_notification(f"Error: {str(e)}", "error")
        if "insufficient_quota" in str(e):
            create_notification("You need to add credits to your OpenAI account", "warning")
        elif "invalid_api_key" in str(e):
            create_notification("Your API key is invalid", "warning")

def test_designer_matching():
    """Test the designer matching functionality"""
    try:
        from designer_selector import suggest_best_designer, load_designers
        
        # Load designers
        designers_df = load_designers()
        if designers_df.empty:
            create_notification("No designers loaded!", "error")
            return
            
        create_notification(f"Loaded {len(designers_df)} designers", "info")
        
        # Test request
        test_request = "Need a PowerPoint presentation in Arabic for a corporate client"
        
        with st.spinner("Testing designer matching..."):
            suggestion = suggest_best_designer(test_request, designers_df, max_designers=3)
            
        create_notification("Designer matching completed!", "success")
        st.text_area("Suggestion:", suggestion, height=200)
        
    except Exception as e:
        create_notification(f"Error in designer matching: {str(e)}", "error")

def test_model(model_name):
    """Test a specific model - Updated for v1.0+"""
    try:
        from openai import OpenAI
        from config import get_secret
        
        api_key = get_secret("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        
        with st.spinner(f"Testing {model_name}..."):
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "What model are you?"}],
                max_tokens=50
            )
            
            create_notification(f"Response: {response.choices[0].message.content}", "success")
            
    except Exception as e:
        create_notification(f"Error testing {model_name}: {str(e)}", "error")
        if "model_not_found" in str(e) or "invalid_request_error" in str(e):
            create_notification(f"Your API key doesn't have access to {model_name}", "warning")
# -------------------------------
# SIDEBAR
# -------------------------------
def render_sidebar():
    import xmlrpc.client
    from config import get_secret
    from session_manager import SessionManager
    import base64
    import os
    
    # Enhanced sidebar styling
    sidebar_style = f"""
    <style>
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #2B1B4C 0%, #6B46E5 100%);
    }}
    
    /* Ensure all text is white */
    section[data-testid="stSidebar"] * {{
        color: white !important;
    }}
    
    section[data-testid="stSidebar"] .stMarkdown {{
        color: white !important;
    }}
    
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4,
    section[data-testid="stSidebar"] h5,
    section[data-testid="stSidebar"] h6,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label {{
        color: white !important;
    }}
    
    /* Style buttons */
    section[data-testid="stSidebar"] .stButton > button {{
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white !important;
        transition: all 0.3s ease;
        width: 100%;
        text-align: left;
        padding: 0.5rem 1rem;
    }}
    
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: rgba(255, 255, 255, 0.2);
        transform: translateX(5px);
    }}
    
    /* Fix caption text */
    section[data-testid="stSidebar"] .stCaption {{
        color: rgba(255, 255, 255, 0.7) !important;
    }}
    </style>
    """
    st.sidebar.markdown(sidebar_style, unsafe_allow_html=True)
    
    # Logo section
    logo_html = ""
    logo_path = "PrezLab-Logos-02.png"
    
    # Check if logo is already in session state
    if hasattr(st.session_state, 'logo_base64') and st.session_state.logo_base64:
        logo_html = f"""
        <div style="text-align: center; margin-bottom: 2rem;">
            <img src="data:image/png;base64,{st.session_state.logo_base64}" 
                 style="width: 40px; height: auto; 
                        background: white; 
                        padding: 3px; 
                        border-radius: 10px;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);">
            <h2 style="color: white; margin-top: 1rem; font-weight: 300; font-size: 1.2rem;">PrezLab TMS</h2>
        </div>
        """
    else:
        # Try to load logo from file
        possible_paths = [
            logo_path,
            os.path.join(".", logo_path),
            os.path.join(os.path.dirname(__file__), logo_path) if '__file__' in globals() else logo_path
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        logo_data = base64.b64encode(f.read()).decode()
                        st.session_state.logo_base64 = logo_data  # Cache for future use
                        logo_html = f"""
                        <div style="text-align: center; margin-bottom: 2rem;">
                            <img src="data:image/png;base64,{logo_data}" 
                                 style="width: 60px; height: auto; 
                                        background: white; 
                                        padding: 6px; 
                                        border-radius: 15px;
                                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);">
                            <h2 style="color: white; margin-top: 1rem; font-weight: 300; font-size: 1.2rem;">PrezLab TMS</h2>
                        </div>
                        """
                        break
                except Exception as e:
                    logger.error(f"Error loading logo: {e}")
    
    # Fallback if no logo found
    if not logo_html:
        logo_html = """
        <div style="text-align: center; margin-bottom: 2rem;">
            <div style="
                background: white;
                width: 60px;
                height: 60px;
                border-radius: 15px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                font-weight: 700;
                color: #805AF9;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);">
                P</div>
            <h2 style="color: white; margin-top: 1rem; font-weight: 300; font-size: 1.2rem;">PrezLab TMS</h2>
        </div>
        <style>
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }
        </style>
        """
    
    st.sidebar.markdown(logo_html, unsafe_allow_html=True)
    st.sidebar.title("Task Management")

    # User Info Section
    st.sidebar.markdown("<h4 style='color: white; margin-bottom: 10px;'>User Info:</h4>", unsafe_allow_html=True)
    
    if st.session_state.get("logged_in", False):
        user_name = st.session_state.get("odoo_credentials", {}).get("name", "Unknown")
        user_email = st.session_state.get("user", {}).get("username", "None")
        
        st.sidebar.markdown(f"<p style='color: white; margin: 5px 0;'><b>Name:</b> {user_name}</p>", unsafe_allow_html=True)
        st.sidebar.markdown(f"<p style='color: white; margin: 5px 0;'><b>Email:</b> {user_email}</p>", unsafe_allow_html=True)
        
        # Session expiry
        expiry = st.session_state.get("session_expiry")
        if expiry:
            st.sidebar.markdown(f"<p style='color: white; margin: 5px 0;'><b>Session expires:</b> {expiry.strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown("<p style='color: white; font-style: italic;'>Not logged in</p>", unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # Navigation & Auth (only if logged in)
    if st.session_state.get("logged_in", False):
        # Navigation
        # Navigation
        st.sidebar.subheader("Navigation")
        if st.sidebar.button("🏠 Home"):
            # Clear all flow-related session state to return to type selection
            SessionManager.clear_flow_data()
            # Also clear these specific keys to ensure clean navigation
            keys_to_clear = [
                "form_type", 
                "company_selection_done", 
                "adhoc_sales_order_done",
                "adhoc_parent_input_done", 
                "retainer_parent_input_done",
                "designer_selection",
                "email_analysis_done",
                "email_analysis_skipped",
                "created_tasks",
                "parent_task_id",
                "subtask_index",
                "adhoc_subtasks"
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    st.session_state.pop(key, None)
            st.rerun()

        # Admin Tools for 'admin' user
        if st.session_state.user.get("username") == "admin":
            st.sidebar.markdown("---")
            st.sidebar.subheader("Admin Tools")
            if st.sidebar.button("🐛 System Debug Dashboard"):
                st.session_state.debug_mode = "system_debug"
                st.rerun()
            if st.sidebar.button("🔐 Auth Debug Dashboard"):
                st.session_state.debug_mode = "auth_debug"
                st.rerun()
    else:
        st.sidebar.info("Please log in to access navigation.")

    # Quick Debug (always visible)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Debug")
    
    if st.sidebar.button("Test Supabase"):
        try:
            from token_storage import test_supabase_connection
            result, message = test_supabase_connection()
            if result:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

    if st.sidebar.button("Test Encryption"):
        try:
            from token_storage import encrypt_token, decrypt_token
            test_data = {"test": "data"}
            encrypted = encrypt_token(test_data)
            if encrypted:
                decrypted = decrypt_token(encrypted)
                if decrypted == test_data:
                    st.sidebar.success("✅ Encryption working!")
                else:
                    st.sidebar.error("❌ Decryption mismatch")
            else:
                st.sidebar.error("❌ Encryption failed")
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

    if st.sidebar.button("Test Odoo Secrets"):
        for key in ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]:
            val = get_secret(key)
            if val:
                st.sidebar.markdown(f"<p style='color: white;'>✅ <b>{key}</b> is set</p>", unsafe_allow_html=True)
            else:
                st.sidebar.markdown(f"<p style='color: white;'>❌ <b>{key}</b> is EMPTY</p>", unsafe_allow_html=True)

    if st.sidebar.button("Test Odoo Connection"):
        try:
            # Try to get credentials from session state first
            odoo_credentials = st.session_state.get('odoo_credentials', {})
            if odoo_credentials:
                url = odoo_credentials['url'] + "/xmlrpc/2/common"
                uid = xmlrpc.client.ServerProxy(url).authenticate(
                    odoo_credentials['db'],
                    odoo_credentials['email'],
                    odoo_credentials['password'],
                    {}
                )
                st.sidebar.success(f"✅ Connected! UID: {uid}")
            else:
                # Fallback to secrets
                url = get_secret("ODOO_URL") + "/xmlrpc/2/common"
                uid = xmlrpc.client.ServerProxy(url).authenticate(
                    get_secret("ODOO_DB"),
                    get_secret("ODOO_USERNAME"),
                    get_secret("ODOO_PASSWORD"),
                    {}
                )
                st.sidebar.success(f"✅ authenticate() → {uid!r}")
        except Exception as e:
            st.sidebar.error(f"❌ RPC error: {type(e).__name__}: {e}")

    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 PrezLab TMS")
    
    # Debug info at bottom
    st.sidebar.markdown("<h5 style='color: white; margin-top: 20px;'>Debug Info:</h5>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='color: rgba(255,255,255,0.7); font-size: 12px;'>Logged in: {st.session_state.get('logged_in', False)}</p>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='color: rgba(255,255,255,0.7); font-size: 12px;'>Username: {st.session_state.get('user', {}).get('username', 'None')}</p>", unsafe_allow_html=True)
    
    # Show session expiry if available
    expiry = st.session_state.get("session_expiry")
    if expiry:
        st.sidebar.markdown(f"<p style='color: rgba(255,255,255,0.7); font-size: 12px;'>Session expires at: {expiry.strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)

def auth_debug_page():
    """Dashboard for authentication debugging"""
    st.title("Authentication Debug Dashboard")
    
    # Basic Authentication Info
    st.subheader("Authentication Status")
    
    # Display current authentication state
    auth_state = {
        "Logged In": st.session_state.get("logged_in", False),
        "Username": st.session_state.get("user", {}).get("username", "None"),
        "Gmail Auth Complete": st.session_state.get("gmail_auth_complete", False),
        "Drive Auth Complete": st.session_state.get("drive_auth_complete", False),
        "Google Auth Complete": st.session_state.get("google_auth_complete", False),
        "Gmail Credentials Present": "google_gmail_creds" in st.session_state,
        "Drive Credentials Present": "google_drive_creds" in st.session_state
    }
    
    for key, value in auth_state.items():
        st.write(f"**{key}:** {value}")

    # In the auth_debug_page function, add:
    st.subheader("Token Reset")
    if st.button("Reset All OAuth Tokens"):
        from token_storage import reset_user_tokens
        success = reset_user_tokens()
        if success:
            # Also clear local session tokens
            for key in ["google_gmail_creds", "google_drive_creds", 
                        "gmail_auth_complete", "drive_auth_complete", 
                        "google_auth_complete"]:
                if key in st.session_state:
                    del st.session_state[key]
            create_notification("All tokens reset successfully. Please re-authenticate.", "success")
        else:
            create_notification("Failed to reset tokens. Check logs for details.", "error")
    
    # Supabase Testing
    st.subheader("Supabase Connection Test")
    
    if st.button("Test Supabase Connection"):
        try:
            from token_storage import get_supabase_client
            client = get_supabase_client()
            if client:
                try:
                    response = client.table("oauth_tokens").select("count").limit(1).execute()
                    create_notification("✅ Supabase connection successful", "success")
                    st.json(response.data)
                except Exception as e:
                    create_notification(f"❌ Table error: {str(e)}", "error")
            else:
                create_notification("❌ Supabase client creation failed", "error")
        except Exception as e:
            create_notification(f"❌ Error: {str(e)}", "error")
    
    # Test encryption
    st.subheader("Encryption Test")
    
    if st.button("Test Encryption System"):
        try:
            from token_storage import get_encryption_key, encrypt_token, decrypt_token
            
            # Get encryption key
            key = get_encryption_key()
            if key:
                create_notification(f"✅ Encryption key found (length: {len(key)})", "success")
                
                # Test encryption/decryption
                import time as time_module  # Add this near your other imports
                # Then use:
                test_data = {"test": "data", "time": str(time_module.time())}
                st.write("Test data:", test_data)
                
                encrypted = encrypt_token(test_data)
                if encrypted:
                    create_notification(f"✅ Encryption successful", "success")
                    st.text(f"Encrypted data preview: {encrypted[:50]}...")
                    
                    decrypted = decrypt_token(encrypted)
                    if decrypted == test_data:
                        create_notification("✅ Decryption successful", "success")
                        st.write("Decrypted data:", decrypted)
                    else:
                        create_notification("❌ Decryption failed or mismatched", "error")
                        st.write("Decrypted data:", decrypted)
                else:
                    create_notification("❌ Encryption failed", "error")
            else:
                create_notification("❌ No encryption key found", "error")
                secrets_keys = list(st.secrets.keys())
                st.write("Available secret keys:", secrets_keys)
        except Exception as e:
            create_notification(f"❌ Error: {str(e)}", "error")
            st.code(traceback.format_exc())
    # In app.py, add this section to your auth_debug_page() function:

    # After the existing sections (Supabase Connection Test, Encryption Test, etc.), add:

    # OpenAI API Testing
    st.subheader("OpenAI API Test")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Configuration:**")
        
        # Check API key
        api_key = get_secret("OPENAI_API_KEY")
        if api_key:
            create_notification(f"✅ API Key found", "success")
            st.code(f"{api_key[:20]}...{api_key[-4:]}")
            
            # Validate key format
            if api_key.startswith("sk-") and len(api_key) > 40:
                create_notification("✅ Key format looks valid", "success")
            else:
                create_notification("⚠️ Key format might be invalid", "warning")
        else:
            create_notification("❌ No API key found", "error")
            create_notification("Add OPENAI_API_KEY to your secrets.toml", "info")
        
        # Show model configuration
        model = get_secret("OPENAI_MODEL", "gpt-4")
        create_notification(f"Default model: {model}", "info")
        
        # Show OpenAI version
        try:
            import openai
            create_notification(f"OpenAI library: v{getattr(openai, '__version__', 'unknown')}", "info")
        except ImportError:
            create_notification("❌ OpenAI library not installed", "error")

    with col2:
        st.write("**Quick Tests:**")
        
        if st.button("Test OpenAI Connection"):
            try:
                import openai
                openai.api_key = api_key
                
                with st.spinner("Calling OpenAI API..."):
                    # For openai 0.28.0
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "user", "content": "Respond with 'OpenAI is working!' and nothing else."}
                        ],
                        max_tokens=10,
                        temperature=0
                    )
                    
                    result = response.choices[0].message.content
                    create_notification(f"✅ API Response: {result}", "success")
                    
                    # Show token usage
                    if hasattr(response, 'usage'):
                        st.json({
                            "tokens_used": response.usage.total_tokens,
                            "model": response.model,
                            "response_id": response.id
                        })
                        
            except Exception as e:
                create_notification(f"❌ Error: {str(e)}", "error")
                
                # Specific error handling
                error_msg = str(e).lower()
                if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                    create_notification("💳 **No credits!** Add funds to your OpenAI account at https://platform.openai.com/account/billing", "error")
                elif "invalid_api_key" in error_msg or "incorrect api key" in error_msg:
                    create_notification("🔑 **Invalid API key!** Get a new key at https://platform.openai.com/api-keys", "error")
                elif "model_not_found" in error_msg:
                    create_notification("🤖 **Model not available!** Your API key might not have access to this model.", "error")
                else:
                    st.code(str(e))
        
        if st.button("Test Designer Selector"):
            try:
                from designer_selector import load_designers, simple_skill_match
                
                # Load designers
                designers_df = load_designers()
                if not designers_df.empty:
                    create_notification(f"✅ Loaded {len(designers_df)} designers", "success")
                    
                    # Test skill matching
                    test_request = "PowerPoint presentation in Arabic"
                    designer = designers_df.iloc[0]
                    score = simple_skill_match(test_request, designer)
                    
                    create_notification(f"Test match score for {designer['Name']}: {score}%", "info")
                else:
                    create_notification("❌ No designers loaded", "error")
                    
            except Exception as e:
                create_notification(f"❌ Designer selector error: {str(e)}", "error")

    # Add a log viewer for OpenAI-specific logs
    with st.expander("OpenAI Debug Logs"):
        try:
            with open('designer_selector.log', 'r') as f:
                logs = f.readlines()
                # Filter for OpenAI-related logs
                openai_logs = [log for log in logs if 'openai' in log.lower() or 'api' in log.lower()]
                st.text_area("Recent OpenAI logs:", '\n'.join(openai_logs[-20:]), height=200)
        except:
            create_notification("No logs available", "info")
    # Google Auth Actions
    st.subheader("Google Authentication Actions")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset Google Auth State"):
            keys = ["google_gmail_creds", "google_drive_creds", 
                    "gmail_auth_complete", "drive_auth_complete", "google_auth_complete"]
            for key in keys:
                if key in st.session_state:
                    del st.session_state[key]
            create_notification("Google authentication state reset", "success")
            st.rerun()
    
    with col2:
        if st.button("Start Google Auth Process"):
            st.session_state.show_google_auth = True
            st.rerun()
    
    # Add ability to return to normal mode
    if st.button("Return to Normal Mode"):
        st.session_state.pop("debug_mode", None)
        st.rerun()        
# -------------------------------
# 1) LOGIN PAGE
# -------------------------------

def login_page():
    from session_manager import SessionManager

    # Touch the session so we don't expire mid-login
    SessionManager.update_activity()
    
    if "login_in_progress" in st.session_state:
        return
    
    inject_enhanced_css()
    style_form_container()
    
    # Center the form in the middle column
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Try to use the existing add_logo function
        try:
            # First, let's create a container for centered logo
            st.markdown(
                """
                <div style="display: flex; justify-content: center; margin-bottom: 2rem;">
                    <div id="logo-container"></div>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            # If logo is in session state, use it
            if hasattr(st.session_state, 'logo_base64') and st.session_state.logo_base64:
                logo_html = f"""
                <div style="text-align: center; margin-bottom: 2rem; animation: float 3s ease-in-out infinite;">
                    <img src="data:image/png;base64,{st.session_state.logo_base64}" 
                         style="width: 150px; height: auto;">
                </div>
                <style>
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px); }}
                    50% {{ transform: translateY(-10px); }}
                }}
                </style>
                """
                st.markdown(logo_html, unsafe_allow_html=True)
            else:
                # Try to load logo using add_logo function
                add_logo(position="center", width=150)
        except Exception as e:
            # Fallback animated logo if add_logo fails
            logger.error(f"Error loading logo: {e}")
            logo_html = f"""
            <div style="text-align: center; margin-bottom: 2rem;">
                <div style="
                    width: 120px;
                    height: 120px;
                    margin: 0 auto;
                    background: linear-gradient(135deg, {COLORS['primary_purple']} 0%, {COLORS['dark_purple']} 100%);
                    border-radius: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 10px 30px rgba(128, 90, 249, 0.3);
                    animation: float 3s ease-in-out infinite;
                ">
                    <span style="color: white; font-size: 60px; font-weight: 700;">P</span>
                </div>
            </div>
            <style>
            @keyframes float {{
                0%, 100% {{ transform: translateY(0px); }}
                50% {{ transform: translateY(-10px); }}
            }}
            </style>
            """
            st.markdown(logo_html, unsafe_allow_html=True)
        
        # Use animated header
        create_animated_header("Welcome to PrezLab", "Task Management System")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Login form with enhanced styling
        with st.form("login_form", clear_on_submit=False):
            # Form container styling
            form_container = """
            <style>
            /* Enhanced form field styling */
            div[data-testid="stForm"] {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 2rem;
                box-shadow: 0 8px 32px rgba(128, 90, 249, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            
            /* Input field styling */
            div[data-testid="stForm"] input {
                background: white !important;
                border: 2px solid #E4E3FF !important;
                border-radius: 12px !important;
                padding: 12px 16px !important;
                font-size: 16px !important;
                transition: all 0.3s ease !important;
            }
            
            div[data-testid="stForm"] input:focus {
                border-color: #805AF9 !important;
                box-shadow: 0 0 0 3px rgba(128, 90, 249, 0.1) !important;
            }
            
            /* Label styling */
            div[data-testid="stForm"] label {
                color: #2B1B4C !important;
                font-weight: 600 !important;
                margin-bottom: 8px !important;
            }
            
            /* Submit button special styling */
            div[data-testid="stForm"] button[type="submit"] {
                background: linear-gradient(135deg, #805AF9 0%, #6B46E5 100%) !important;
                color: white !important;
                border: none !important;
                padding: 12px 24px !important;
                border-radius: 50px !important;
                font-weight: 600 !important;
                font-size: 16px !important;
                width: 100% !important;
                margin-top: 1rem !important;
                transition: all 0.3s ease !important;
                box-shadow: 0 4px 15px rgba(128, 90, 249, 0.3) !important;
            }
            
            div[data-testid="stForm"] button[type="submit"]:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 20px rgba(128, 90, 249, 0.4) !important;
            }
            </style>
            """
            st.markdown(form_container, unsafe_allow_html=True)
            
            # Form fields with icons
            st.markdown(
                """
                <div style="margin-bottom: 1rem;">
                    <label style="color: #2B1B4C; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">📧</span> Email
                    </label>
                </div>
                """, 
                unsafe_allow_html=True
            )
            email = st.text_input("Email", key="email_input", placeholder="your.email@company.com", label_visibility="collapsed")
            
            st.markdown(
                """
                <div style="margin-bottom: 1rem;">
                    <label style="color: #2B1B4C; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">🔒</span> Password
                    </label>
                </div>
                """, 
                unsafe_allow_html=True
            )
            password = st.text_input("Password", type="password", key="password_input", label_visibility="collapsed")
            
            st.markdown(
                """
                <div style="margin-bottom: 1rem;">
                    <label style="color: #2B1B4C; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">🌐</span> Odoo URL
                    </label>
                </div>
                """, 
                unsafe_allow_html=True
            )
            odoo_url = st.text_input("Odoo URL", key="odoo_url_input", 
                                    value="https://prezlab-staging-19128678.dev.odoo.com",
                                    help="Enter your Odoo instance URL",
                                    label_visibility="collapsed")
            
            # Submit button
            submit = st.form_submit_button("Sign In", use_container_width=True)

            if not submit:
                return

            # Validation
            if not email or not password or not odoo_url:
                create_notification("Please enter all fields.", "warning")
                return

            # Try to authenticate with Odoo
            try:
                import xmlrpc.client
                
                # Show loading animation
                with st.spinner("Authenticating..."):
                    # Extract database name from URL
                    import re
                    db_match = re.search(r'https://([^.]+)(?:-\d+)?\.', odoo_url)
                    if db_match:
                        odoo_db = db_match.group(1)
                        # Handle staging/production URLs
                        if '-staging-' in odoo_url:
                            db_parts = odoo_url.split('.')[0].split('//')[-1]
                            odoo_db = db_parts
                    else:
                        create_notification("Could not extract database name from URL. Please contact support.", "error")
                        return
                    
                    # Test connection
                    common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common", allow_none=True)
                    uid = common.authenticate(odoo_db, email, password, {})
                    
                    if not uid:
                        create_notification("Invalid credentials. Please check your email and password.", "error")
                        return
                    
                    # Get user's name from Odoo
                    models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object", allow_none=True)
                    user_info = models.execute_kw(
                        odoo_db, uid, password,
                        'res.users', 'read',
                        [[uid]],
                        {'fields': ['name', 'email']}
                    )
                    
                    user_name = user_info[0]['name'] if user_info else email
                    
                    # Store Odoo credentials in session state
                    st.session_state.odoo_credentials = {
                        'url': odoo_url,
                        'db': odoo_db,
                        'email': email,
                        'password': password,
                        'uid': uid,
                        'name': user_name
                    }
                    
                    # Log into Streamlit session using email as username
                    SessionManager.login(email, expiry_hours=8)
                    
                    # Success animation
                    success_html = f"""
                    <div style="text-align: center; margin: 1rem 0;">
                        <div style="
                            width: 60px;
                            height: 60px;
                            margin: 0 auto;
                            background: linear-gradient(135deg, {COLORS['success']} 0%, {COLORS['green']} 100%);
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            animation: scaleIn 0.5s ease;
                        ">
                            <span style="color: white; font-size: 30px;">✓</span>
                        </div>
                    </div>
                    <style>
                    @keyframes scaleIn {{
                        0% {{ transform: scale(0); opacity: 0; }}
                        100% {{ transform: scale(1); opacity: 1; }}
                    }}
                    </style>
                    """
                    st.markdown(success_html, unsafe_allow_html=True)
                    
                    create_notification(f"Welcome, {user_name}!", "success")
                    st.rerun()
                    
            except Exception as e:
                create_notification(f"Connection failed: {str(e)}", "error")
                logger.exception("Odoo login error")
                return

        # Footer
        st.markdown(
            f"""
            <div style="text-align: center; margin-top: 3rem; color: {COLORS['dark_gray']};">
                <p style="font-size: 14px;">
                    Need help? Contact your system administrator<br>
                    © 2025 PrezLab TMS - All rights reserved
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
# -------------------------------
# 2) REQUEST TYPE SELECTION PAGE
# -------------------------------
def type_selection_page():

    inject_enhanced_css()

    # ADD this instead:
    user_name = st.session_state.get('odoo_credentials', {}).get('name', st.session_state.user['username'])
    create_animated_header(f"Welcome back, {user_name}!", "What would you like to create today?")
    

    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container(border=True):
            st.subheader("Via Sales Order")
            st.markdown("For one-time projects or framework tasks with subtasks.")
            if st.button("Create Ad-hoc Request", use_container_width=True):
                st.session_state.form_type = "Via Sales Order"
                st.rerun()
    
    with col2:
        with st.container(border=True):
            st.subheader("Via Project")
            st.markdown("For ongoing projects with recurring tasks.")
            if st.button("Create Retainer Request", use_container_width=True):
                st.session_state.form_type = "Via Project"
                st.rerun()
                
    # Recent activities section
    with st.expander("Recent Activities", expanded=False):
        st.markdown("This section will show recent task activities.")
        # Here you could display recent tasks from Odoo

# -------------------------------
# HELPER: Fetch Sales Order Lines
# -------------------------------
def get_sales_order_lines(models, uid, sales_order_name):
    try:
        odoo_db = st.session_state.odoo_credentials['db']
        odoo_password = st.session_state.odoo_credentials['password']
        
        so_data = models.execute_kw(
            odoo_db, uid, odoo_password,
            'sale.order', 'search_read',
            [[['name', '=', sales_order_name]]],
            {'fields': ['order_line']}
        )
        if not so_data:
            return []
        order_line_ids = so_data[0].get('order_line', [])
        if not order_line_ids:
            return []
        lines = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,  # Fixed: Using constants instead of os.getenv
            'sale.order.line', 'read',
            [order_line_ids],
            {'fields': ['id', 'name']}
        )
        return lines
    except Exception as e:
        logger.error(f"Error fetching sales order lines: {e}")
        create_notification(f"Error fetching sales order lines. Please try again.", "error")
        return []

# -------------------------------
# 3A) SALES ORDER PAGE (Ad-hoc Step 1)
# -------------------------------
def sales_order_page():

    inject_enhanced_css()
    
    
    create_animated_header("Via Sales Order", "Select Sales Order")

    # Progress bar
    create_progress_steps(
        current_step=2,
        total_steps=5,
        step_labels=["Company", "Sales Order", "Email Analysis", "Parent Task", "Subtasks"]
    ) 
        
    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            # Set a flag to indicate we're returning to parent (don't clear the form data)
            st.session_state.pop("company_selection_done", None)
            st.rerun()
    
    # Display selected company
    def display_company():
        st.markdown(f"**Selected Company:** {st.session_state.get('selected_company', '')}")

    create_glass_card(content=display_company, title="Current Selection", icon="🏢")
    selected_company = st.session_state.get("selected_company", "")

    # Add this code to detect company changes and force refresh
    if "last_company_for_sales_orders" in st.session_state:
        if st.session_state.last_company_for_sales_orders != selected_company:
            # Company changed, force refresh sales orders
            st.session_state.refresh_sales_orders = True
            
    # Update the tracked company
    st.session_state.last_company_for_sales_orders = selected_company

    # Connect to Odoo
    if "odoo_uid" not in st.session_state or "odoo_models" not in st.session_state:
        with st.spinner("Connecting to Odoo..."):
            uid, models = authenticate_odoo()
            if uid and models:
                st.session_state.odoo_uid = uid
                st.session_state.odoo_models = models
            else:
                create_notification("Failed to connect to Odoo. Please check your credentials.", "error")
                return
    else:
        uid = st.session_state.odoo_uid
        models = st.session_state.odoo_models

    # Fetch sales orders filtered by company if not already in session
    if "sales_orders" not in st.session_state or st.session_state.get("refresh_sales_orders", False):
        with st.spinner("Fetching sales orders..."):
            orders = get_sales_orders(models, uid, selected_company)
            if orders:
                st.session_state.sales_orders = orders
                st.session_state.refresh_sales_orders = False
            else:
                create_notification(f"No sales orders found for {selected_company} or error fetching orders.", "warning")
                st.session_state.sales_orders = []

    # Create form for sales order selection
    style_form_container()
    with st.form("sales_order_form"):
        st.subheader("Select Sales Order")
        
        sales_order_options = [order['name'] for order in st.session_state.sales_orders]
        selected_sales_order = st.selectbox(
            "Sales Order Number",
            ["(Manual Entry)"] + sales_order_options
        )

        # We're not showing these fields anymore, but we need placeholder 
        # variables that will hold the values later
        parent_sales_order_item = None
        customer = None
        project = None

        submit = st.form_submit_button("Next")
        
        if submit:
            # If a sales order is selected, get the details from Odoo
            if selected_sales_order != "(Manual Entry)":
                details = get_sales_order_details(models, uid, selected_sales_order)
                parent_sales_order_item = details.get('sales_order', selected_sales_order)
                customer = details.get('customer', "")
                project = details.get('project', "")
                
                # For automatic sales order selection, we use the order name itself if no item specified
                if not parent_sales_order_item:
                    parent_sales_order_item = selected_sales_order
            else:
                # For manual entry, we use the selected_sales_order as the item name
                # This removes the validation problem since we're not showing the fields to fill
                parent_sales_order_item = "Manual Entry"
                customer = "Manual Customer"
                project = "Manual Project"
            
            # Save to session state
            st.session_state.parent_sales_order_item = parent_sales_order_item
            st.session_state.customer = customer
            st.session_state.project = project
            
            # Get sales order lines for selected order
            if selected_sales_order != "(Manual Entry)":
                with st.spinner("Fetching sales order lines..."):
                    so_lines = get_sales_order_lines(models, uid, selected_sales_order)
            else:
                so_lines = []
                
            st.session_state.so_items = so_lines
            st.session_state.subtask_index = 0
            st.session_state.adhoc_subtasks = []
            st.session_state.adhoc_sales_order_done = True
            create_notification("Sales order information saved. Proceeding to parent task details.", "success")
            st.rerun()

# -------------------------------
# 3B) AD-HOC PARENT TASK PAGE (Ad-hoc Step 2)
# -------------------------------
# In app.py, replace the adhoc_parent_task_page() function with this updated version:

def adhoc_parent_task_page():
    inject_enhanced_css()
    create_animated_header("Via Sales Order", "Parent Task Details")
    
    # Progress bar
    create_progress_steps(
        current_step=4,
        total_steps=5,
        step_labels=["Company", "Sales Order", "Email Analysis", "Parent Task", "Subtasks"]
    )
    
    # Clear the return flag if it exists
    st.session_state.pop("returning_to_parent", False) if "returning_to_parent" in st.session_state else None

    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            st.session_state.pop("adhoc_sales_order_done", None)
            st.rerun()

    def display_current_selection():
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**Company:** {st.session_state.get('selected_company', '')}")
        with col2:
            st.markdown(f"**Sales Order:** {st.session_state.get('parent_sales_order_item', '')}")
        with col3:
            st.markdown(f"**Customer:** {st.session_state.get('customer', '')}")
        with col4:
            st.markdown(f"**Project:** {st.session_state.get('project', '')}")

    create_glass_card(content=display_current_selection, title="Current Selection", icon="📋")
    
    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models

    # Use confirmed suggestions if available
    email_analysis = st.session_state.get("email_analysis_confirmed") or st.session_state.get("email_analysis", {})
    email_analysis_skipped = st.session_state.get("email_analysis_skipped", True)

    # Form for parent task details
    style_form_container()
    with st.form("parent_task_form"):
        st.subheader("Parent Task Details")
        
        # Basic Information
        with st.container():
            # Use enhanced email analysis results
            default_title = ""
            if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
                # Use the AI-suggested parent task title
                default_title = email_analysis.get("parent_task_title", "")
                if not default_title:
                    # Fallback to services-based title
                    services = email_analysis.get("services", "")
                    client = email_analysis.get("client", "")
                    if services and client:
                        default_title = f"{services} for {client}"
                    elif services:
                        default_title = f"Task for {services}"
            
            parent_task_title = st.text_input("Parent Task Title", 
                                             value=default_title,
                                             help="AI-suggested title based on email analysis")
            
            col1, col2 = st.columns(2)
            with col1:
                target_language_options = get_target_languages_odoo(models, uid)
                # Enhanced target language detection
                default_target_lang_idx = 0
                if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
                    target_lang = email_analysis.get("target_language", "")
                    if target_lang and target_language_options:
                        # Try exact match first
                        for i, lang in enumerate(target_language_options):
                            if target_lang.lower() == lang.lower():
                                default_target_lang_idx = i + 1  # +1 because of empty option
                                break
                        # If no exact match, try partial match
                        if default_target_lang_idx == 0:
                            for i, lang in enumerate(target_language_options):
                                if target_lang.lower() in lang.lower() or lang.lower() in target_lang.lower():
                                    default_target_lang_idx = i + 1
                                    break
                
                target_language_parent = st.selectbox(
                    "Target Language", 
                    [""] + target_language_options if target_language_options else [""],
                    index=default_target_lang_idx,
                    help="Auto-detected from email if available"
                )
            with col2:
                client_success_exec_options = get_client_success_executives_odoo(models, uid)
                
                # Get logged-in user info
                logged_in_email = st.session_state.get("user", {}).get("username", "")
                logged_in_name = st.session_state.get("odoo_credentials", {}).get("name", "")
                
                # Find the logged-in user in the executives list
                default_exec_index = 0
                default_exec_value = None
                
                if client_success_exec_options and logged_in_email:
                    exec_options = [(None, "")] + [(user['id'], user['name']) for user in client_success_exec_options]
                    
                    # Try to find by email or name
                    for i, (user_id, user_name) in enumerate(exec_options):
                        if user_id is not None:  # Skip the empty option
                            # Check if the name matches or if email is in the name
                            if (user_name == logged_in_name or 
                                logged_in_email.lower() in user_name.lower() or
                                logged_in_name.lower() in user_name.lower()):
                                default_exec_index = i
                                default_exec_value = (user_id, user_name)
                                break
                    
                    # If we found a match and this is the first time showing the form
                    if default_exec_value and "adhoc_exec_set" not in st.session_state:
                        st.session_state.adhoc_default_exec = default_exec_value
                        st.session_state.adhoc_exec_set = True
                    
                    # Use stored default or found default
                    if "adhoc_default_exec" in st.session_state:
                        default_exec_value = st.session_state.adhoc_default_exec
                        # Find its index
                        for i, option in enumerate(exec_options):
                            if option == default_exec_value:
                                default_exec_index = i
                                break
                    
                    client_success_executive = st.selectbox(
                        "Client Success Executive", 
                        options=exec_options,
                        index=default_exec_index,
                        format_func=lambda x: x[1],
                        help="Automatically set to logged-in user"
                    )
                else:
                    # Fallback to text input
                    client_success_executive = st.text_input("Client Success Executive", value=logged_in_name)
        
        # Guidelines
        with st.expander("Guidelines", expanded=False):
            guidelines_options = get_guidelines_odoo(models, uid)
            if guidelines_options:
                # Add empty option at the beginning
                guidelines_options_with_empty = [(None, "")] + guidelines_options
                # Use format_func to display the name while storing the tuple
                guidelines_parent = st.selectbox(
                    "Guidelines", 
                    options=guidelines_options_with_empty,
                    format_func=lambda x: x[1]  # Display the name part
                )
            else:
                create_notification("No guidelines found. This field is required.", "error")
                guidelines_parent = None
                
        # Dates section with AI suggestions
        st.subheader("Task Timeline")
        col1, col2, col3 = st.columns(3)
        
        # Calculate suggested dates based on email analysis
        default_client_due = date.today() + pd.Timedelta(days=7)
        default_internal_due = date.today() + pd.Timedelta(days=5)
        
        if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
            urgency = email_analysis.get("urgency", "medium").lower()
            
            # Adjust dates based on urgency
            if urgency == "high":
                default_client_due = date.today() + pd.Timedelta(days=3)
                default_internal_due = date.today() + pd.Timedelta(days=2)
            elif urgency == "low":
                default_client_due = date.today() + pd.Timedelta(days=14)
                default_internal_due = date.today() + pd.Timedelta(days=10)
            
            # Show urgency indicator
            urgency_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(urgency, "🟡")
            st.info(f"{urgency_color} Urgency: {urgency.capitalize()} (AI-detected)")
        
        with col1:
            request_receipt_date = st.date_input("Request Receipt Date", value=date.today())
            request_receipt_time = st.time_input("Request Receipt Time", value=datetime.now().time())
        with col2:
            client_due_date_parent = st.date_input("Client Due Date", 
                                                  value=default_client_due,
                                                  help="AI-suggested based on email urgency")
        with col3:
            internal_due_date = st.date_input("Internal Due Date", 
                                             value=default_internal_due,
                                             help="AI-suggested (2-3 days before client deadline)")
        
        # Combine date and time
        request_receipt_dt = datetime.combine(request_receipt_date, request_receipt_time)
        
        # Enhanced description with email analysis
        st.subheader("Description")
        
        # Build comprehensive description from email analysis
        default_description = ""
        if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
            # Start with requirements
            requirements = email_analysis.get("requirements", "")
            if requirements:
                default_description = f"Requirements from client email:\n{requirements}"
            
            # Add services
            services = email_analysis.get("services", "")
            if services:
                default_description += f"\n\nRequested Services:\n{services}"
            
            # Add deadline info
            client_deadline = email_analysis.get("client_deadline", "")
            if client_deadline:
                default_description += f"\n\nClient Requested Deadline: {client_deadline}"
            
            # Add contact person
            contact = email_analysis.get("contact_person", "")
            if contact:
                default_description += f"\n\nContact Person: {contact}"
            
            # Add any additional notes
            notes = email_analysis.get("additional_notes", "")
            if notes:
                default_description += f"\n\nAdditional Notes:\n{notes}"
            
            # Add attachments mentioned
            attachments = email_analysis.get("attachments_mentioned", "")
            if attachments:
                default_description += f"\n\nAttachments/References Mentioned: {attachments}"
        
        parent_description = st.text_area("Task Description", 
                                         value=default_description,
                                         height=200, 
                                         help="Auto-populated from email analysis")
        
        # Show AI-suggested subtasks if available
        if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
            subtask_suggestions = email_analysis.get("subtask_suggestions", [])
            if subtask_suggestions and len(subtask_suggestions) > 0:
                with st.expander("📋 AI-Suggested Subtasks", expanded=True):
                    st.write("The AI has suggested the following subtasks based on the email:")
                    for i, suggestion in enumerate(subtask_suggestions, 1):
                        st.write(f"{i}. {suggestion}")
                    st.info("These suggestions will be used when creating subtasks in the next step.")
                    
        # Submit button
        submit = st.form_submit_button("Next: Add Subtasks")
        
        if submit:
            # Validate inputs
            if not parent_task_title:
                create_notification("Please enter a parent task title.", "error")
                return
            
            # Check if required fields are selected (not None or empty)
            if not target_language_parent:
                create_notification("Please select a target language.", "error")
                return
                
            if client_success_executive is None or (isinstance(client_success_executive, tuple) and client_success_executive[0] is None):
                create_notification("Please select a client success executive.", "error")
                return
                
            if guidelines_parent is None or (isinstance(guidelines_parent, tuple) and guidelines_parent[0] is None):
                create_notification("Please select guidelines.", "error")
                return
            # Save to session state
            st.session_state.adhoc_parent_task_title = parent_task_title
            st.session_state.adhoc_target_language = target_language_parent
            st.session_state.adhoc_guidelines = guidelines_parent
            st.session_state.adhoc_client_success_exec = client_success_executive
            st.session_state.adhoc_request_receipt_dt = request_receipt_dt
            st.session_state.adhoc_client_due_date_parent = client_due_date_parent
            st.session_state.adhoc_internal_due_date = internal_due_date
            st.session_state.adhoc_parent_description = parent_description
            st.session_state.adhoc_parent_input_done = True
            
            create_notification("Parent task details saved. Proceeding to subtasks.", "success")
            st.rerun()

# -------------------------------
# 3C) AD-HOC SUBTASK PAGE (Ad-hoc Step 3)
# -------------------------------
# In app.py, replace the adhoc_subtask_page() function with this updated version:

def adhoc_subtask_page():
    inject_enhanced_css()
    create_animated_header("Adhoc Subtask Page", "Create the subtasks")    
    
    # Progress bar
    create_progress_steps(
        current_step=5,
        total_steps=5,
        step_labels=["Company", "Sales Order", "Email Analysis", "Parent Task", "Subtasks"]
    )
    
    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            st.session_state.pop("adhoc_parent_input_done", None)
            st.rerun()

    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models

    # Get parent task information
    parent_data = {
        "selected_company": st.session_state.get("selected_company", ""),
        "parent_sales_order_item": st.session_state.get("parent_sales_order_item", ""),
        "parent_task_title": st.session_state.get("adhoc_parent_task_title", ""),
        "customer": st.session_state.get("customer", ""),
        "project": st.session_state.get("project", ""),
        "target_language_parent": st.session_state.get("adhoc_target_language", ""),
        "guidelines_parent": st.session_state.get("adhoc_guidelines", ""),
        "client_success_executive": st.session_state.get("adhoc_client_success_exec", ""),
        "request_receipt_dt": st.session_state.get("adhoc_request_receipt_dt", datetime.now()),
        "client_due_date_parent": st.session_state.get("adhoc_client_due_date_parent", date.today()),
        "internal_due_date": st.session_state.get("adhoc_internal_due_date", date.today()),
        "parent_description": st.session_state.get("adhoc_parent_description", "")
    }
    
    # Display parent task summary
    with st.expander("Parent Task Summary", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Company:** {parent_data['selected_company']}")
            st.markdown(f"**Parent Task:** {parent_data['parent_task_title']}")
            st.markdown(f"**Sales Order:** {parent_data['parent_sales_order_item']}")
            st.markdown(f"**Customer:** {parent_data['customer']}")
            st.markdown(f"**Project:** {parent_data['project']}")
            st.markdown(f"**Target Language:** {parent_data['target_language_parent']}")
        with col2:
            st.markdown(f"**Client Success Executive:** {parent_data['client_success_executive'][1] if isinstance(parent_data['client_success_executive'], tuple) else parent_data['client_success_executive']}")
            st.markdown(f"**Request Receipt:** {parent_data['request_receipt_dt'].strftime('%Y-%m-%d %H:%M')}")
            st.markdown(f"**Client Due Date:** {parent_data['client_due_date_parent']}")
            st.markdown(f"**Internal Due Date:** {parent_data['internal_due_date']}")
        
        st.markdown(f"**Description:** {parent_data['parent_description']}")

    # Get current subtask index and sales order items list
    idx = st.session_state.get("subtask_index", 0)
    so_items = st.session_state.get("so_items", [])
    
    # Use confirmed suggestions if available
    email_analysis = st.session_state.get("email_analysis_confirmed") or st.session_state.get("email_analysis", {})
    email_analysis_skipped = st.session_state.get("email_analysis_skipped", True)
    subtask_suggestions = []
    if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
        subtask_suggestions = email_analysis.get("subtask_suggestions", [])
    
    # Display subtasks in progress
    if st.session_state.adhoc_subtasks:
        def display_subtasks():
            for i, task in enumerate(st.session_state.adhoc_subtasks):
                st.markdown(f"**Subtask {i+1}:** {task['subtask_title']} (Due: {task['client_due_date_subtask']})")
        
        create_glass_card(content=display_subtasks, title="Subtasks Added", icon="✅")
    
    # Check if we have more subtasks to add
    if idx >= len(so_items):
        create_notification("No more sales order items available for subtasks.", "warning")
        
        # Allow adding a custom subtask if needed
        with st.expander("Add Custom Subtask", expanded=True):
            style_form_container()
            with st.form("custom_subtask_form"):
                custom_subtask_title = st.text_input("Custom Subtask Title")
                
                col1, col2 = st.columns(2)
                with col1:
                    service_category_1_options = get_service_category_1_options(models, uid)
                    service_category_1 = st.selectbox(
                        "Service Category 1", 
                        [opt[1] if isinstance(opt, list) and len(opt) > 1 else opt for opt in service_category_1_options] if service_category_1_options else [""]
                    )
                    no_of_design_units_sc1 = st.number_input("Total No. of Design Units (SC1)", min_value=0, step=1)
                
                with col2:
                    service_category_2_options = get_service_category_2_options(models, uid)
                    service_category_2 = st.selectbox(
                        "Service Category 2", 
                        [opt[1] if isinstance(opt, list) and len(opt) > 1 else opt for opt in service_category_2_options] if service_category_2_options else [""]
                    )
                    no_of_design_units_sc2 = st.number_input("Total No. of Design Units (SC2)", min_value=0, step=1)
                
                client_due_date_subtask = st.date_input("Client Due Date (Subtask)", value=date.today() + pd.Timedelta(days=5))
                
                add_custom = st.form_submit_button("Add Custom Subtask")
                
                if add_custom:
                    if not custom_subtask_title:
                        create_notification("Please enter a subtask title.", "error")
                        return
                        
                    new_subtask = {
                        "line_id": None,
                        "line_name": "Custom",
                        "subtask_title": custom_subtask_title,
                        "service_category_1": service_category_1,
                        "no_of_design_units_sc1": no_of_design_units_sc1,
                        "service_category_2": service_category_2,
                        "no_of_design_units_sc2": no_of_design_units_sc2,
                        "client_due_date_subtask": str(client_due_date_subtask)
                    }
                    st.session_state.adhoc_subtasks.append(new_subtask)
                    create_notification(f"Added custom subtask: {custom_subtask_title}", "success")
                    st.rerun()
        
        # Show submission button
        if st.button("Submit All Tasks", use_container_width=True, type="primary"):
            loading_placeholder = st.empty()
            with loading_placeholder.container():
                show_loading_animation("Creating tasks in Odoo...")
            finalize_adhoc_subtasks()
            loading_placeholder.empty()
        
        return
    
    # Current sales order line for this subtask
    current_line = so_items[idx] if idx < len(so_items) else {}
    line_name = current_line.get("name", f"Line #{idx+1}") if current_line else f"Subtask #{idx+1}"
    
    # Subtask form
    style_form_container()
    with st.form(f"subtask_form_{idx}"):
        st.subheader(f"Subtask for Sales Order Line: {line_name}")
        
        # Smart default title using AI suggestions
        default_title = f"Subtask for {line_name}"
        
        # Use AI-suggested subtask name if available
        if subtask_suggestions and idx < len(subtask_suggestions):
            default_title = subtask_suggestions[idx]
        elif email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
            # Fallback: generate title based on service and line
            services = email_analysis.get("services", "")
            if services and idx == 0:  # First subtask
                default_title = f"Initial Planning - {services}"
            elif services and idx == 1:  # Second subtask
                default_title = f"Design/Development - {services}"
            elif idx == len(so_items) - 1:  # Last subtask
                default_title = f"Final Review and Delivery"
            else:
                default_title = f"{services} - Part {idx + 1}" if services else default_title
                
        subtask_title = st.text_input("Subtask Title", value=default_title)
        
        col1, col2 = st.columns(2)
        with col1:
            service_category_1_options = get_service_category_1_options(models, uid)
            
            # Try to auto-select service category based on email analysis
            default_sc1_idx = 0
            if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
                suggested_sc1 = email_analysis.get("service_category_1", "")
                if suggested_sc1 and service_category_1_options:
                    # Try to find matching category
                    for i, (cat_id, cat_name) in enumerate(service_category_1_options):
                        if suggested_sc1.lower() in cat_name.lower() or cat_name.lower() in suggested_sc1.lower():
                            default_sc1_idx = i + 1  # +1 for the None option
                            break
            
            if service_category_1_options:
                # Add empty option as first choice
                service_category_1 = st.selectbox(
                    "Service Category 1", 
                    options=[None] + service_category_1_options,
                    index=default_sc1_idx,
                    format_func=lambda x: "" if x is None else (x[1] if isinstance(x, tuple) and len(x) > 1 else str(x)),
                    help="Auto-selected based on email analysis" if default_sc1_idx > 0 else None
                )
            else:
                # Fallback to text input with warning
                create_notification("No service categories found. Manual entry not recommended.", "warning")
                service_category_1_text = st.text_input("Service Category 1 (manual)")
                service_category_1 = (-1, service_category_1_text) if service_category_1_text else None
            
            # Auto-suggest design units based on email analysis
            default_units_sc1 = 0
            if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
                design_units = email_analysis.get("design_units", "")
                if design_units:
                    try:
                        # Try to parse number from string
                        import re
                        numbers = re.findall(r'\d+', str(design_units))
                        if numbers:
                            default_units_sc1 = int(numbers[0])
                    except:
                        pass
            
            no_of_design_units_sc1 = st.number_input("Total No. of Design Units (SC1)", 
                                                     min_value=0, 
                                                     step=1, 
                                                     value=default_units_sc1,
                                                     help="Auto-estimated from email" if default_units_sc1 > 0 else None)

        with col2:
            service_category_2_options = get_service_category_2_options(models, uid)
            
            # Similar logic for service category 2
            default_sc2_idx = 0
            if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
                suggested_sc2 = email_analysis.get("service_category_2", "")
                if suggested_sc2 and service_category_2_options:
                    for i, (cat_id, cat_name) in enumerate(service_category_2_options):
                        if suggested_sc2.lower() in cat_name.lower() or cat_name.lower() in suggested_sc2.lower():
                            default_sc2_idx = i + 1
                            break
            
            if service_category_2_options:
                service_category_2 = st.selectbox(
                    "Service Category 2", 
                    options=[None] + service_category_2_options,
                    index=default_sc2_idx,
                    format_func=lambda x: "" if x is None else (x[1] if isinstance(x, tuple) and len(x) > 1 else str(x))
                )
            else:
                service_category_2_text = st.text_input("Service Category 2 (manual)")
                service_category_2 = (-1, service_category_2_text) if service_category_2_text else None
            
            no_of_design_units_sc2 = st.number_input("Total No. of Design Units (SC2)", min_value=0, step=1)
        
        # Auto-suggest due date based on urgency
        default_subtask_due = date.today() + pd.Timedelta(days=5)
        if email_analysis and isinstance(email_analysis, dict) and not email_analysis_skipped:
            urgency = email_analysis.get("urgency", "medium").lower()
            if urgency == "high":
                default_subtask_due = date.today() + pd.Timedelta(days=2)
            elif urgency == "low":
                default_subtask_due = date.today() + pd.Timedelta(days=10)
        
        client_due_date_subtask = st.date_input("Client Due Date (Subtask)", 
                                               value=default_subtask_due,
                                               help="Auto-adjusted based on email urgency")
        
        # Submit options
        col1, col2 = st.columns(2)
        with col1:
            # Only show "Save & Next Subtask" if there are more subtasks
            if idx < len(so_items) - 1:
                next_subtask = st.form_submit_button("Save & Next Subtask")
            else:
                next_subtask = False
        with col2:
            if idx == len(so_items) - 1:
                finish_all = st.form_submit_button("Finish & Submit All")
            else:
                finish_all = False
        
        if next_subtask or finish_all:
            # Validate input
            if not subtask_title:
                create_notification("Please enter a subtask title.", "error")
                return
                
            # Create new subtask
            new_subtask = {
                "line_id": current_line.get("id"),
                "line_name": line_name,
                "subtask_title": subtask_title,
                "service_category_1": service_category_1,
                "no_of_design_units_sc1": no_of_design_units_sc1,
                "service_category_2": service_category_2,
                "no_of_design_units_sc2": no_of_design_units_sc2,
                "client_due_date_subtask": str(client_due_date_subtask)
            }
            
            # Add to session state
            st.session_state.adhoc_subtasks.append(new_subtask)
            st.session_state.subtask_index = idx + 1
            
            # If finishing, submit all; otherwise, continue to next subtask
            if finish_all:
                finalize_adhoc_subtasks()
            else:
                create_notification(f"Subtask saved: {subtask_title}", "success")
                st.rerun()
# -------------------------------
# Finalize: Create Parent Task & Subtasks in Odoo
# -------------------------------
def finalize_adhoc_subtasks():
    from session_manager import SessionManager
    SessionManager.update_activity()
    
    # Import modules only when needed
    from google_drive import create_folder_structure
    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models

    loading_placeholder = st.empty()

    # Get parent task data
    selected_company = st.session_state.get("selected_company", "")
    parent_sales_order_item = st.session_state.get("parent_sales_order_item", "")
    parent_task_title = st.session_state.get("adhoc_parent_task_title", "")
    customer = st.session_state.get("customer", "")
    project_name = st.session_state.get("project", "")
    target_language_parent = st.session_state.get("adhoc_target_language", "")
    guidelines_parent = st.session_state.get("adhoc_guidelines", "")
    client_success_executive = st.session_state.get("adhoc_client_success_exec", "")
    request_receipt_dt = st.session_state.get("adhoc_request_receipt_dt", datetime.now())
    client_due_date_parent = st.session_state.get("adhoc_client_due_date_parent", date.today())
    internal_due_date = st.session_state.get("adhoc_internal_due_date", date.today())
    parent_description = st.session_state.get("adhoc_parent_description", "")

    try:
        # Step 1: Create parent task
        # Removed spinner for 'Creating tasks in Odoo...'
        # Get project ID
        project_id = get_project_id_by_name(models, uid, project_name)
        if not project_id:
            create_notification(f"Could not find project with name: {project_name}", "error")
            return
            
        # Ensure project_id is integer
        if not isinstance(project_id, int):
            try:
                project_id = int(project_id)
            except (ValueError, TypeError) as e:
                create_notification(f"Invalid project ID format: {e}", "error")
                logger.error(f"Invalid project ID format: {project_id}, error: {e}")
                return
        
        # Handle user ID
        user_id = client_success_executive[0] if isinstance(client_success_executive, tuple) and client_success_executive[0] is not None else client_success_executive
        if user_id is None:
            create_notification("Invalid client success executive selection", "error")
            return
        if not isinstance(user_id, int):
            try:
                user_id = int(user_id)
            except (ValueError, TypeError) as e:
                create_notification(f"Invalid user ID format: {e}", "error")
                logger.error(f"Invalid user ID format: {user_id}, error: {e}")
                return
        
        # Handle guidelines_id - make sure it's an integer
        guidelines_id = guidelines_parent[0] if isinstance(guidelines_parent, tuple) else None
        
        # Create parent task with only fields that exist
        parent_task_data = {
            "name": f"Ad-hoc Parent: {parent_task_title}",
            "project_id": project_id,
            "user_ids": [(6, 0, [user_id])],  # This is the correct format for many2many fields
            "description": f"Company: {selected_company}\nSales Order Item: {parent_sales_order_item}\nCustomer: {customer}\nProject: {project_name}\n{parent_description}"
        }
        
        # Add optional fields if they exist and have values
        if target_language_parent:
            parent_task_data["x_studio_target_language"] = target_language_parent
            
        if guidelines_id:
            parent_task_data["x_studio_guidelines"] = guidelines_id
        
        # Format dates correctly to avoid the microseconds issue
        if request_receipt_dt:
            parent_task_data["x_studio_request_receipt_date_time"] = request_receipt_dt.strftime("%Y-%m-%d %H:%M:%S")
            
        if client_due_date_parent:
            parent_task_data["x_studio_client_due_date_3"] = client_due_date_parent.strftime("%Y-%m-%d")
            
        if internal_due_date:
            parent_task_data["x_studio_internal_due_date_1"] = internal_due_date.strftime("%Y-%m-%d")
        
        # Create parent task in Odoo
        parent_task_id = create_odoo_task(parent_task_data)
        if not parent_task_id:
            create_notification("Failed to create parent task in Odoo.", "error")
            return
            
        create_notification(f"Created Parent Task in Odoo (ID: {parent_task_id})", "success")
        
        # Create Google Drive folder structure for this parent task
        with loading_placeholder.container():
            show_loading_animation("Creating Google Drive folders...")
        # Sanitize folder name (replace characters not allowed in file names)
        folder_name = f"{parent_task_title} - {parent_task_id}"
        folder_name = folder_name.replace('/', '-').replace('\\', '-')
            
        # Create folder structure with subfolders
        from google_drive import create_folder_structure
        folder_structure = create_folder_structure(
            folder_name, 
            subfolders=["MATERIAL", "DELIVERABLE"]
        )
            
        if folder_structure:
            # Store main folder info in session state
            st.session_state.drive_folder_id = folder_structure['main_folder_id']
            st.session_state.drive_folder_link = folder_structure['main_folder_link']
            st.session_state.folder_structure = folder_structure
                
            # Update the parent task with the folder links
            try:
                # Create a nicely formatted description with folder links
                updated_description = f"{parent_description}\n\n"
                updated_description += f"📁 **Google Drive Folders:**\n"
                updated_description += f"- Main Folder: {folder_structure['main_folder_url']}\n"
                    
                # Add subfolder links if available
                for subfolder_name, subfolder_info in folder_structure['subfolders'].items():
                    updated_description += f"- {subfolder_name}: {subfolder_info['url']}\n"
                    
                models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'project.task', 'write',
                    [[parent_task_id], {'description': updated_description}]
                )
                logger.info(f"Updated task {parent_task_id} with Drive folder structure links")
            except Exception as e:
                logger.warning(f"Could not update task with folder links: {e}")
                    
            create_notification(f"Created folder structure with MATERIAL and DELIVERABLE subfolders", "success")
        else:
            create_notification("Could not create Google Drive folder. Please check logs for details.", "warning")
        
        with loading_placeholder.container():
            show_loading_animation("Creating subtasks in Odoo...")

        # Create subtasks
        subtasks = st.session_state.adhoc_subtasks
        created_subtasks = []
        
        for i, sub in enumerate(subtasks):
            # Create base subtask data
            subtask_data = {
                "name": f"Ad-hoc Subtask: {sub['subtask_title']}",
                "project_id": project_id,
                "user_ids": [(6, 0, [user_id])],
                "description": f"Company: {selected_company}\nSubtask for Sales Order Line: {sub['line_name']}",
                # Set the parent-child relationship - use parent_id, not x_studio_sub_task_1
                "parent_id": parent_task_id
            }
            
            # Add optional fields if they exist and have values
            if target_language_parent:
                subtask_data["x_studio_target_language"] = target_language_parent
                
            if guidelines_id:
                subtask_data["x_studio_guidelines"] = guidelines_id
            
            # Format dates correctly
            if request_receipt_dt:
                subtask_data["x_studio_request_receipt_date_time"] = request_receipt_dt.strftime("%Y-%m-%d %H:%M:%S")
                
            # Use the subtask-specific due date
            if "client_due_date_subtask" in sub and sub["client_due_date_subtask"]:
                # Parse the date from string if needed
                if isinstance(sub["client_due_date_subtask"], str):
                    due_date = datetime.strptime(sub["client_due_date_subtask"], "%Y-%m-%d").date()
                else:
                    due_date = sub["client_due_date_subtask"]
                subtask_data["x_studio_client_due_date_3"] = due_date.strftime("%Y-%m-%d")
                
            if internal_due_date:
                subtask_data["x_studio_internal_due_date_1"] = internal_due_date.strftime("%Y-%m-%d")
            
            # Add service categories if they exist
            if "service_category_1" in sub and sub["service_category_1"]:
                # If service_category_1 is a tuple with ID and name, use the ID
                if isinstance(sub["service_category_1"], tuple) and len(sub["service_category_1"]) > 1:
                    # Only use the ID if it's valid (not -1)
                    if sub["service_category_1"][0] != -1:
                        subtask_data["x_studio_service_category_1"] = sub["service_category_1"][0]
                    else:
                        logger.warning(f"Skipping invalid service_category_1 ID: {sub['service_category_1']}")
                # If it's already an ID, use it directly
                elif isinstance(sub["service_category_1"], int):
                    subtask_data["x_studio_service_category_1"] = sub["service_category_1"]
                else:
                    logger.warning(f"Skipping service_category_1 as it's not in the expected format: {sub['service_category_1']}")

            # Similar handling for service_category_2
            if "service_category_2" in sub and sub["service_category_2"]:
                if isinstance(sub["service_category_2"], tuple) and len(sub["service_category_2"]) > 1:
                    # Only use the ID if it's valid (not -1)
                    if sub["service_category_2"][0] != -1:
                        subtask_data["x_studio_service_category_2"] = sub["service_category_2"][0]
                    else:
                        logger.warning(f"Skipping invalid service_category_2 ID: {sub['service_category_2']}")
                elif isinstance(sub["service_category_2"], int):
                    subtask_data["x_studio_service_category_2"] = sub["service_category_2"]
                else:
                    logger.warning(f"Skipping service_category_2 as it's not in the expected format: {sub['service_category_2']}")
            
            # Add design units if applicable
            if "no_of_design_units_sc1" in sub and sub["no_of_design_units_sc1"]:
                subtask_data["x_studio_total_no_of_design_units_sc1"] = sub["no_of_design_units_sc1"]
            
            if "no_of_design_units_sc2" in sub and sub["no_of_design_units_sc2"]:
                subtask_data["x_studio_total_no_of_design_units_sc2"] = sub["no_of_design_units_sc2"]
            
            # Create subtask in Odoo
            subtask_id = create_odoo_task(subtask_data)
            if subtask_id:
                created_subtasks.append(subtask_id)
                create_notification(f"Created Subtask {i+1} in Odoo (ID: {subtask_id})", "success")
            else:
                create_notification(f"Failed to create subtask {i+1} in Odoo.", "error")
        loading_placeholder.empty()
        # After tasks are created successfully
        if created_subtasks:
            create_notification(f"Successfully created {len(created_subtasks)} subtasks!", "success")
            
            # Store created tasks and parent task ID in session state for designer selection
            created_tasks = []
            for subtask_id in created_subtasks:
                # Fetch the task details from Odoo
                task_details = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'project.task', 'read',
                    [[subtask_id]],
                    {'fields': ['id', 'name', 'description', 'x_studio_service_category_1', 
                            'x_studio_service_category_2', 'x_studio_target_language',
                            'x_studio_client_due_date_3', 'date_deadline']}
                )[0]
                created_tasks.append(task_details)
            
            # Store in session state
            st.session_state.created_tasks = created_tasks
            st.session_state.parent_task_id = parent_task_id
            st.session_state.designer_selection = True
            
            # Summary container
            def display_task_summary():
                st.markdown(f"**Parent Task:** {parent_task_title} (ID: {parent_task_id})")
                st.markdown(f"**Subtasks Created:** {len(created_subtasks)}")
                st.markdown(f"**Company:** {selected_company}")
                st.markdown(f"**Project:** {project_name}")
                st.markdown(f"**Client:** {customer}")
                
                if 'drive_folder_id' in st.session_state and 'drive_folder_link' in st.session_state:
                    st.markdown(f"**📁 Main Folder:** [Open Folder]({st.session_state.drive_folder_link})")
                    
                    # If we have subfolder information, display those links too
                    if 'folder_structure' in st.session_state and 'subfolders' in st.session_state.folder_structure:
                        for subfolder_name, subfolder_info in st.session_state.folder_structure['subfolders'].items():
                            st.markdown(f"**📁 {subfolder_name}:** [Open Folder]({subfolder_info['link']})")

            create_glass_card(content=display_task_summary, title="Task Creation Summary", icon="✅")

            # Keep the display message OUTSIDE the glass card
            create_notification("Click the button below to proceed to designer selection, or you can view the task details in Odoo.", "info")
            st.session_state.designer_selection = True  # This flag is already being checked elsewhere
            st.rerun()


    except Exception as e:
        loading_placeholder.empty()  # Clear on error too
        create_notification(f"An error occurred: {str(e)}", "error")
        logger.error(f"Error in finalize_adhoc_subtasks: {e}", exc_info=True)

# -------------------------------
# RETAINER FLOW
# -------------------------------
# In app.py, replace the retainer_parent_task_page() function with this updated version:

def retainer_parent_task_page():
    inject_enhanced_css()
    create_animated_header("Retainer Parent Task Page", "Create the parent task")
    
    # Progress bar
    create_progress_steps(
        current_step=3,
        total_steps=4,
        step_labels=["Company", "Parent Task", "Subtask", "Complete"]
    )    
    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            st.session_state.returning_to_company = True
            st.rerun()
            
    # Display selected company
    def display_company():
        st.markdown(f"**Selected Company:** {st.session_state.get('selected_company', '')}")

    create_glass_card(content=display_company, title="Current Selection", icon="🏢")
    
    selected_company = st.session_state.get("selected_company", "")

    # Add this code to detect company changes and force refresh
    if "last_company_for_sales_orders" in st.session_state:
        if st.session_state.last_company_for_sales_orders != selected_company:
            # Company changed, force refresh sales orders
            st.session_state.refresh_sales_orders = True
            
    # Update the tracked company
    st.session_state.last_company_for_sales_orders = selected_company

    # Connect to Odoo if not already connected
    if "odoo_uid" not in st.session_state or "odoo_models" not in st.session_state:
        with st.spinner("Connecting to Odoo..."):
            uid, models = authenticate_odoo()
            if uid and models:
                st.session_state.odoo_uid = uid
                st.session_state.odoo_models = models
            else:
                create_notification("Failed to connect to Odoo. Please check your credentials.", "error")
                return
    else:
        uid = st.session_state.odoo_uid
        models = st.session_state.odoo_models

    # Form for retainer parent task
    style_form_container()
    with st.form("retainer_parent_form"):
        st.subheader("Retainer Project Fields")
        
        # Project and customer selection
        col1, col2 = st.columns(2)
        with col1:
            retainer_project_options = get_retainer_projects(models, uid, selected_company)
            if retainer_project_options:
                parent_project = st.selectbox("Project", retainer_project_options)
            else:
                parent_project = st.text_input("Project")
        
        with col2:
            retainer_customer_options = get_retainer_customers(models, uid)
            if retainer_customer_options:
                retainer_customer = st.selectbox("Customer", retainer_customer_options)
            else:
                retainer_customer = st.text_input("Customer")
        
        parent_task_title = st.text_input("Parent Task Title")
        
        # Language and executive
        col1, col2 = st.columns(2)
        with col1:
            target_language_options = get_target_languages_odoo(models, uid)
            if target_language_options:
                retainer_target_language = st.selectbox("Target Language", [""] + target_language_options)
            else:
                retainer_target_language = st.text_input("Target Language")
        
        with col2:
            client_success_exec_options = get_client_success_executives_odoo(models, uid)
            
            # Get logged-in user info
            logged_in_email = st.session_state.get("user", {}).get("username", "")
            logged_in_name = st.session_state.get("odoo_credentials", {}).get("name", "")
            
            # Find the logged-in user in the executives list
            default_exec_index = 0
            default_exec_value = None
            
            if client_success_exec_options and logged_in_email:
                exec_options = [(None, "")] + [(user['id'], user['name']) for user in client_success_exec_options]
                
                # Try to find by email or name
                for i, (user_id, user_name) in enumerate(exec_options):
                    if user_id is not None:  # Skip the empty option
                        # Check if the name matches or if email is in the name
                        if (user_name == logged_in_name or 
                            logged_in_email.lower() in user_name.lower() or
                            logged_in_name.lower() in user_name.lower()):
                            default_exec_index = i
                            default_exec_value = (user_id, user_name)
                            break
                
                # If we found a match and this is the first time showing the form
                if default_exec_value and "retainer_exec_set" not in st.session_state:
                    st.session_state.retainer_default_exec = default_exec_value
                    st.session_state.retainer_exec_set = True
                
                # Use stored default or found default
                if "retainer_default_exec" in st.session_state:
                    default_exec_value = st.session_state.retainer_default_exec
                    # Find its index
                    for i, option in enumerate(exec_options):
                        if option == default_exec_value:
                            default_exec_index = i
                            break
                
                retainer_client_success_exec = st.selectbox(
                    "Client Success Executive", 
                    options=exec_options,
                    index=default_exec_index,
                    format_func=lambda x: x[1],
                    help="Automatically set to logged-in user"
                )
            else:
                # Fallback to text input
                retainer_client_success_exec = st.text_input("Client Success Executive", value=logged_in_name)
        
        # Guidelines
        with st.expander("Guidelines", expanded=False):
            guidelines_options = get_guidelines_odoo(models, uid)
            if guidelines_options:
                # Add empty option at the beginning
                guidelines_options_with_empty = [(None, "")] + guidelines_options
                # Use format_func to display only the name while storing the tuple
                retainer_guidelines = st.selectbox(
                    "Guidelines", 
                    options=guidelines_options_with_empty,
                    format_func=lambda x: x[1]  # Display the name part
                )
            else:
                retainer_guidelines = st.text_area("Guidelines", height=100)
        
        # Dates
        st.subheader("Dates (Retainer Parent Task)")
        
        col1, col2 = st.columns(2)
        with col1:
            retainer_request_receipt_date = st.date_input("Request Receipt Date", value=date.today())
            retainer_request_receipt_time = st.time_input("Request Receipt Time", value=datetime.now().time())
        
        with col2:
            retainer_internal_due_date = st.date_input("Internal Due Date", value=date.today() + pd.Timedelta(days=5))
            retainer_internal_due_time = st.time_input("Internal Due Time", value=time(17, 0))  # 5:00 PM default
        
        # Combine date and time
        retainer_request_receipt_dt = datetime.combine(retainer_request_receipt_date, retainer_request_receipt_time)
        retainer_internal_dt = datetime.combine(retainer_internal_due_date, retainer_internal_due_time)
        
        # Submit button
        submit = st.form_submit_button("Next: Add Subtask")
        
        if submit:
            # Validate input
            if not parent_project or not parent_task_title or not retainer_customer:
                create_notification("Please fill in all required fields.", "error")
                return
            
            # Check if required dropdowns are selected
            if not retainer_target_language:
                create_notification("Please select a target language.", "error")
                return
                
            if retainer_client_success_exec is None or (isinstance(retainer_client_success_exec, tuple) and retainer_client_success_exec[0] is None):
                create_notification("Please select a client success executive.", "error")
                return
                
            if retainer_guidelines is None or (isinstance(retainer_guidelines, tuple) and retainer_guidelines[0] is None):
                create_notification("Please select guidelines.", "error")
                return
                
            # Save to session state
            st.session_state.retainer_project = parent_project
            st.session_state.retainer_parent_task_title = parent_task_title
            st.session_state.retainer_customer = retainer_customer
            st.session_state.retainer_target_language = retainer_target_language
            st.session_state.retainer_guidelines = retainer_guidelines
            st.session_state.retainer_client_success_exec = retainer_client_success_exec
            st.session_state.retainer_request_receipt_dt = retainer_request_receipt_dt
            st.session_state.retainer_internal_dt = retainer_internal_dt
            st.session_state.retainer_parent_input_done = True
            
            create_notification("Parent task details saved. Proceeding to subtask.", "success")
            st.rerun()
            
def retainer_subtask_page():
    inject_enhanced_css() 
    create_animated_header("Retainer Subtask Page", "Create the subtasks")
    
    # Progress bar
    create_progress_steps(
        current_step=4,
        total_steps=4,
        step_labels=["Company", "Parent Task", "Subtask", "Complete"]
    )
    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            st.session_state.pop("retainer_parent_input_done", None)
            st.rerun()

    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models

    # Get parent task information
    selected_company = st.session_state.get("selected_company", "")
    parent_project_name = st.session_state.get("retainer_project", "")
    parent_task_title = st.session_state.get("retainer_parent_task_title", "")
    retainer_customer = st.session_state.get("retainer_customer", "")
    retainer_target_language = st.session_state.get("retainer_target_language", "")
    retainer_guidelines = st.session_state.get("retainer_guidelines", "")
    retainer_client_success_exec = st.session_state.get("retainer_client_success_exec", "")
    retainer_request_receipt_dt = st.session_state.get("retainer_request_receipt_dt", datetime.now())
    retainer_internal_dt = st.session_state.get("retainer_internal_dt", datetime.now())

    # Display parent task summary
    # Display parent task summary
    def display_parent_summary():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Company:** {selected_company}")
            st.markdown(f"**Project:** {parent_project_name}")
            st.markdown(f"**Parent Task:** {parent_task_title}")
            st.markdown(f"**Customer:** {retainer_customer}")
        with col2:
            st.markdown(f"**Target Language:** {retainer_target_language}")
            st.markdown(f"**Request Receipt:** {retainer_request_receipt_dt.strftime('%Y-%m-%d %H:%M')}")
            st.markdown(f"**Internal Due Date:** {retainer_internal_dt.strftime('%Y-%m-%d %H:%M')}")

    create_glass_card(content=display_parent_summary, title="Parent Task Summary", icon="📋")
    # Subtask form
    style_form_container()
    with st.form("retainer_subtask_form"):
        st.subheader("Subtask Details")
        
        subtask_title = st.text_input("Subtask Title")
        
        # Service categories
        col1, col2 = st.columns(2)
        with col1:
            service_category_1_options = get_service_category_1_options(models, uid)
            if service_category_1_options:
                # Add empty option as first choice
                retainer_service_category_1 = st.selectbox(
                    "Service Category 1", 
                    options=[None] + service_category_1_options,
                    format_func=lambda x: "" if x is None else (x[1] if isinstance(x, tuple) and len(x) > 1 else str(x))
                )
            else:
                retainer_service_category_1 = st.text_input("Service Category 1")
            
            no_of_design_units_sc1 = st.number_input("No. of Design Units SC1", min_value=0, step=1)

        with col2:
            service_category_2_options = get_service_category_2_options(models, uid)
            if service_category_2_options:
                # Add empty option as first choice
                retainer_service_category_2 = st.selectbox(
                    "Service Category 2", 
                    options=[None] + service_category_2_options,
                    format_func=lambda x: "" if x is None else (x[1] if isinstance(x, tuple) and len(x) > 1 else str(x))
                )
            else:
                retainer_service_category_2 = st.text_input("Service Category 2")
            
            no_of_design_units_sc2 = st.number_input("No. of Design Units SC2", min_value=0, step=1)
        
        # Due date
        retainer_client_due_date_subtask = st.date_input("Client Due Date (Subtask)")
        
        # Designer suggestion and submit buttons
        col1, col2 = st.columns(2)

        with col2:
            submit_request = st.form_submit_button("Submit Request")
        
        
        # SUBMIT BUTTON HANDLER - Replace the existing submit_request button handler
        if submit_request:
            # Validate inputs
            if not subtask_title:
                create_notification("Please enter a subtask title.", "error")
                return
                
            # Get project ID
            project_id = get_project_id_by_name(models, uid, parent_project_name)
            if not project_id:
                create_notification(f"Could not find a project with name: {parent_project_name}", "error")
                return
                
            # Ensure project_id is integer
            if not isinstance(project_id, int):
                try:
                    project_id = int(project_id)
                except (ValueError, TypeError) as e:
                    create_notification(f"Invalid project ID format: {e}", "error")
                    logger.error(f"Invalid project ID format: {project_id}, error: {e}")
                    return
            
            # Handle user ID
            user_id = retainer_client_success_exec[0] if isinstance(retainer_client_success_exec, tuple) and retainer_client_success_exec[0] is not None else retainer_client_success_exec
            if user_id is None:
                create_notification("Invalid client success executive selection", "error")
                return
            if not isinstance(user_id, int):
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError) as e:
                    create_notification(f"Invalid user ID format: {e}", "error")
                    logger.error(f"Invalid user ID format: {user_id}, error: {e}")
                    return
            
            # Find partner_id for customer if available
            partner_id = None
            try:
                partners = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'res.partner', 'search_read',
                    [[['name', '=', retainer_customer]]],
                    {'fields': ['id']}
                )
                if partners:
                    partner_id = partners[0]['id']
                    logger.info(f"Found partner_id {partner_id} for customer {retainer_customer}")
            except Exception as e:
                logger.warning(f"Could not find partner_id for customer {retainer_customer}: {e}")
            
            try:
                # STEP 1: CREATE PARENT TASK
                with st.spinner("Creating parent task in Odoo..."):
                    # Create parent task with only fields that exist
                    parent_task_data = {
                        "name": f"Retainer Parent: {parent_project_name} - {retainer_customer}",
                        "project_id": project_id,
                        "user_ids": [(6, 0, [user_id])],  # This is the correct format for many2many fields
                        "description": f"Company: {selected_company}\nCustomer: {retainer_customer}\nProject: {parent_project_name}"
                    }
                    
                    # Add partner_id if found
                    if partner_id:
                        parent_task_data["partner_id"] = partner_id
                    
                    # Add optional fields if they exist and have values
                    if retainer_target_language:
                        parent_task_data["x_studio_target_language"] = retainer_target_language
                    
                    # Handle guidelines properly - extract ID from tuple if applicable
                    if retainer_guidelines:
                        if isinstance(retainer_guidelines, tuple) and len(retainer_guidelines) > 1:
                            # Extract the ID (first element of the tuple)
                            if retainer_guidelines[0] is not None:
                                parent_task_data["x_studio_guidelines"] = retainer_guidelines[0]
                        elif isinstance(retainer_guidelines, int):
                            parent_task_data["x_studio_guidelines"] = retainer_guidelines
                        else:
                            logger.warning(f"Guidelines not in expected format: {retainer_guidelines}")
                    # Format dates correctly to avoid the microseconds issue
                    if retainer_request_receipt_dt:
                        parent_task_data["x_studio_request_receipt_date_time"] = retainer_request_receipt_dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                    if retainer_internal_dt:
                        parent_task_data["x_studio_internal_due_date_1"] = retainer_internal_dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Create parent task in Odoo
                    parent_task_id = create_odoo_task(parent_task_data)
                    if not parent_task_id:
                        create_notification("Failed to create parent task in Odoo.", "error")
                        return
                        
                    create_notification(f"Created Parent Task in Odoo (ID: {parent_task_id})", "success")
                
                # STEP 2: CREATE SUBTASK
                with st.spinner("Creating subtask in Odoo..."):
                    # Create subtask with parent_id reference
                    subtask_data = {
                        "name": f"Retainer Subtask: {subtask_title}",
                        "project_id": project_id,
                        "parent_id": parent_task_id,  # This establishes the parent-child relationship
                        "user_ids": [(6, 0, [user_id])],
                        "description": f"Company: {selected_company}\nCustomer: {retainer_customer}\nProject: {parent_project_name}\nSubtask: {subtask_title}"
                    }
                    
                    # Add partner_id if found
                    if partner_id:
                        subtask_data["partner_id"] = partner_id
                    
                    # Add optional fields if they exist
                    if retainer_target_language:
                        subtask_data["x_studio_target_language"] = retainer_target_language
                    
                    # Handle guidelines properly - extract ID from tuple if applicable
                    if retainer_guidelines:
                        if isinstance(retainer_guidelines, tuple) and len(retainer_guidelines) > 1:
                            subtask_data["x_studio_guidelines"] = retainer_guidelines[0]
                        elif isinstance(retainer_guidelines, int):
                            subtask_data["x_studio_guidelines"] = retainer_guidelines
                    
                    # Format dates correctly
                    if retainer_request_receipt_dt:
                        subtask_data["x_studio_request_receipt_date_time"] = retainer_request_receipt_dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                    if retainer_client_due_date_subtask:
                        subtask_data["x_studio_client_due_date_3"] = retainer_client_due_date_subtask.strftime("%Y-%m-%d")
                        
                    if retainer_internal_dt:
                        subtask_data["x_studio_internal_due_date_1"] = retainer_internal_dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Handle service category 1
                    if retainer_service_category_1:
                        if isinstance(retainer_service_category_1, tuple) and len(retainer_service_category_1) > 1:
                            if retainer_service_category_1[0] is not None and retainer_service_category_1[0] != -1:
                                subtask_data["x_studio_service_category_1"] = retainer_service_category_1[0]
                            else:
                                logger.warning(f"Skipping invalid service_category_1 ID: {retainer_service_category_1}")
                        elif isinstance(retainer_service_category_1, int):
                            subtask_data["x_studio_service_category_1"] = retainer_service_category_1
                        else:
                            logger.warning(f"Skipping service_category_1 as it's not in expected format: {retainer_service_category_1}")
                    
                    # Handle service category 2
                    if retainer_service_category_2:
                        if isinstance(retainer_service_category_2, tuple) and len(retainer_service_category_2) > 1:
                            if retainer_service_category_2[0] is not None and retainer_service_category_2[0] != -1:
                                subtask_data["x_studio_service_category_2"] = retainer_service_category_2[0]
                            else:
                                logger.warning(f"Skipping invalid service_category_2 ID: {retainer_service_category_2}")
                        elif isinstance(retainer_service_category_2, int):
                            subtask_data["x_studio_service_category_2"] = retainer_service_category_2
                        else:
                            logger.warning(f"Skipping service_category_2 as it's not in expected format: {retainer_service_category_2}")
                    
                    # Add design units
                    if no_of_design_units_sc1:
                        subtask_data["x_studio_total_no_of_design_units_sc1"] = no_of_design_units_sc1
                    
                    if no_of_design_units_sc2:
                        subtask_data["x_studio_total_no_of_design_units_sc2"] = no_of_design_units_sc2
                    
                    # Create subtask in Odoo
                    subtask_id = create_odoo_task(subtask_data)
                    if not subtask_id:
                        create_notification("Failed to create subtask in Odoo.", "error")
                        return
                        
                    create_notification(f"Created Subtask in Odoo (ID: {subtask_id})", "success")
                
                # STEP 3: CREATE GOOGLE DRIVE FOLDER STRUCTURE
                with st.spinner("Creating Google Drive folder structure for task..."):
                    # Sanitize folder name
                    folder_name = f"{parent_project_name} - {subtask_title} - {subtask_id}"
                    folder_name = folder_name.replace('/', '-').replace('\\', '-')
                    
                    # Create folder structure with subfolders
                    from google_drive import create_folder_structure
                    folder_structure = create_folder_structure(
                        folder_name, 
                        subfolders=["MATERIAL", "DELIVERABLE"]
                    )
                    
                    if folder_structure:
                        # Store main folder info in session state
                        st.session_state.drive_folder_id = folder_structure['main_folder_id']
                        st.session_state.drive_folder_link = folder_structure['main_folder_link']
                        st.session_state.folder_structure = folder_structure
                        # Update both parent and subtask with the folder links
                        try:
                            # Create a nicely formatted description with folder links
                            folder_description = f"\n\n📁 **Google Drive Folders:**\n"
                            folder_description += f"- Main Folder: {folder_structure['main_folder_url']}\n"
                            
                            # Add subfolder links if available
                            for subfolder_name, subfolder_info in folder_structure['subfolders'].items():
                                folder_description += f"- {subfolder_name}: {subfolder_info['url']}\n"
                            
                            # Update parent task description
                            parent_task_desc = models.execute_kw(
                                ODOO_DB, uid, ODOO_PASSWORD,
                                'project.task', 'read',
                                [[parent_task_id]],
                                {'fields': ['description']}
                            )[0]['description']
                            
                            updated_parent_desc = f"{parent_task_desc}{folder_description}"
                            
                            models.execute_kw(
                                ODOO_DB, uid, ODOO_PASSWORD,
                                'project.task', 'write',
                                [[parent_task_id], {'description': updated_parent_desc}]
                            )
                            
                            # Update subtask description
                            subtask_desc = models.execute_kw(
                                ODOO_DB, uid, ODOO_PASSWORD,
                                'project.task', 'read',
                                [[subtask_id]],
                                {'fields': ['description']}
                            )[0]['description']
                            
                            updated_subtask_desc = f"{subtask_desc}{folder_description}"
                            
                            models.execute_kw(
                                ODOO_DB, uid, ODOO_PASSWORD,
                                'project.task', 'write',
                                [[subtask_id], {'description': updated_subtask_desc}]
                            )
                            
                            logger.info(f"Updated tasks with Drive folder structure links")
                            create_notification(f"Created folder structure with MATERIAL and DELIVERABLE subfolders", "success")
                        except Exception as e:
                            logger.warning(f"Could not update tasks with folder links: {e}")
                    else:
                        create_notification("Could not create Google Drive folder. Please check logs for details.", "warning")
                
                # STEP 4: PREPARE FOR DESIGNER SELECTION
                with st.spinner("Preparing for designer selection..."):
                    # Fetch the task details from Odoo for designer selection
                    task_details = models.execute_kw(
                        ODOO_DB, uid, ODOO_PASSWORD,
                        'project.task', 'read',
                        [[subtask_id]],
                        {'fields': ['id', 'name', 'description', 'x_studio_service_category_1', 
                                'x_studio_service_category_2', 'x_studio_target_language',
                                'x_studio_client_due_date_3', 'date_deadline']}
                    )[0]
                    
                    # Store in session state
                    st.session_state.created_tasks = [task_details]
                    st.session_state.customer = retainer_customer
                    st.session_state.project = parent_project_name
                    st.session_state.parent_task_id = parent_task_id
                    st.session_state.designer_selection = True
                    
                    # Display designer suggestion if available
                    if "selected_designer" in st.session_state:
                        create_notification(f"Suggested Designer: {st.session_state.selected_designer}", "info")
                    
                    # Success message and transition
                    create_notification("Tasks created successfully! Proceeding to designer selection...", "success")
                    
                    st.rerun()
            
            except Exception as e:
                create_notification(f"An error occurred: {str(e)}", "error")
                logger.error(f"Error in retainer task creation: {e}", exc_info=True)
def inspect_field_values(models, uid, field_name, model_name='project.task', limit=50):
    """
    Inspects the values of a specific field across records to help diagnose type issues.
    
    Args:
        models: Odoo models proxy
        uid: User ID
        field_name: Name of the field to inspect
        model_name: Name of the model to inspect
        limit: Maximum number of records to fetch
        
    Returns:
        Analysis of the field values
    """
    try:
        # First, get field information
        field_info = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model_name, 'fields_get',
            [[field_name]],
            {'attributes': ['string', 'type', 'relation', 'required', 'selection']}
        )
        
        if not field_info or field_name not in field_info:
            return f"Field '{field_name}' not found in model '{model_name}'."
            
        field_details = field_info[field_name]
        field_type = field_details.get('type', 'unknown')
        field_relation = field_details.get('relation', 'none')
        field_required = field_details.get('required', False)
        field_selection = field_details.get('selection', [])
        
        # Fetch records that have this field populated
        records = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model_name, 'search_read',
            [[[(field_name, '!=', False)]]],
            {'fields': ['id', field_name, 'name'], 'limit': limit}
        )
        
        if not records:
            return (
                f"No records found with field '{field_name}' populated.\n"
                f"Field type: {field_type}\n"
                f"Relation model: {field_relation}\n"
                f"Required: {field_required}\n"
                f"Selection options: {field_selection}"
            )
            
        # Analyze the field values
        types_seen = {}
        sample_values = {}
        
        for rec in records:
            value = rec.get(field_name)
            value_type = type(value).__name__
            
            if value_type not in types_seen:
                types_seen[value_type] = 0
                sample_values[value_type] = []
                
            types_seen[value_type] += 1
            
            # Store a few sample values of each type
            if len(sample_values[value_type]) < 3:
                sample_values[value_type].append((rec.get('id'), rec.get('name', 'No Name'), value))
        
        # Generate report
        report = f"Field '{field_name}' Analysis (from {len(records)} records):\n\n"
        report += f"Field type in Odoo: {field_type}\n"
        report += f"Relation model: {field_relation}\n"
        report += f"Required: {field_required}\n"
        
        if field_selection:
            report += "Selection options:\n"
            for option in field_selection:
                report += f"  - {option}\n"
        
        report += "\nValue types found in database:\n"
        
        for t, count in types_seen.items():
            report += f"Type: {t} ({count} records)\n"
            report += "Sample values:\n"
            
            for record_id, record_name, sample in sample_values[t]:
                # Format the sample value for better readability
                if isinstance(sample, list):
                    sample_str = f"[{sample}]"
                else:
                    sample_str = str(sample)
                    
                report += f"  - ID {record_id} ({record_name}): {sample_str}\n"
                
            report += "\n"
            
        # If it's a relation field, provide some examples of how to use it
        if field_type in ['many2one', 'one2many', 'many2many']:
            report += f"\nThis is a {field_type} relation field. Here's how to use it:\n"
            
            if field_type == 'many2one':
                report += "For many2one fields, set the ID of the related record:\n"
                report += f"  task_data['{field_name}'] = 123  # ID of the related {field_relation} record\n"
            elif field_type == 'many2many':
                report += "For many2many fields, use a special command format:\n"
                report += f"  task_data['{field_name}'] = [(6, 0, [123, 456])]  # Replace with these IDs\n"
                report += f"  task_data['{field_name}'] = [(4, 123, 0)]  # Add this ID\n"
            elif field_type == 'one2many':
                report += "For one2many fields, use a special command format:\n"
                report += f"  task_data['{field_name}'] = [(0, 0, {{'field': 'value'}})]  # Create and link a new record\n"
                report += f"  task_data['{field_name}'] = [(1, 123, {{'field': 'value'}})]  # Update linked record with ID 123\n"
                
        return report
        
    except Exception as e:
        return f"Error inspecting field: {str(e)}"
    
def debug_task_fields():
    """
    Debug function to display all available fields on the project.task model
    """
    st.subheader("Debug: Task Fields")
    
    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models
    
    if not uid or not models:
        create_notification("Not connected to Odoo. Please log in first.", "error")
        return
    
    # Add a field inspection section
    st.subheader("Field Value Inspector")
    
    col1, col2 = st.columns(2)
    with col1:
        field_to_inspect = st.text_input("Enter field name to inspect:", value="x_studio_service_category_1")
    with col2:
        model_name = st.text_input("Model name:", value="project.task")
    
    if st.button("Inspect Field Values"):
        with st.spinner("Analyzing field values..."):
            report = inspect_field_values(models, uid, field_to_inspect, model_name)
            st.text_area("Field Analysis", report, height=400)
    
    # Add quick buttons for common problematic fields
    st.subheader("Quick Field Inspection")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Inspect Service Category 1"):
            with st.spinner("Analyzing service category 1..."):
                report = inspect_field_values(models, uid, "x_studio_service_category_1")
                st.text_area("Service Category 1 Analysis", report, height=400)
    
    with col2:
        if st.button("Inspect Service Category 2"):
            with st.spinner("Analyzing service category 2..."):
                report = inspect_field_values(models, uid, "x_studio_service_category_2")
                st.text_area("Service Category 2 Analysis", report, height=400)
    
    with col3:
        if st.button("Inspect User IDs"):
            with st.spinner("Analyzing user_ids field..."):
                report = inspect_field_values(models, uid, "user_ids")
                st.text_area("User IDs Analysis", report, height=400)
                
    # Model discovery - helps find the actual models for related fields
    st.subheader("Model Discovery")
    
    model_prefix = st.text_input("Search for models with prefix:", value="x_")
    
    if st.button("Search Models"):
        with st.spinner("Searching models..."):
            try:
                # This gets all models in Odoo
                model_records = models.execute_kw(
                    ODOO_DB, uid, ODOO_PASSWORD,
                    'ir.model', 'search_read',
                    [[['model', 'like', model_prefix]]],
                    {'fields': ['id', 'model', 'name']}
                )
                
                if model_records:
                    create_notification(f"Found {len(model_records)} models matching '{model_prefix}'", "success")
                    
                    # Display in a table
                    model_data = []
                    for rec in model_records:
                        model_data.append({
                            "ID": rec.get('id'),
                            "Model": rec.get('model'),
                            "Name": rec.get('name')
                        })
                    
                    st.table(pd.DataFrame(model_data))
                else:
                    create_notification(f"No models found matching '{model_prefix}'", "warning")
            except Exception as e:
                create_notification(f"Error searching models: {str(e)}", "error")
    # Import needed constants
    from helpers import ODOO_DB, ODOO_PASSWORD
    
    try:
        with st.spinner("Fetching project.task fields..."):
            fields = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'project.task', 'fields_get',
                [],
                {'attributes': ['string', 'type', 'required', 'relation']}
            )
        
        create_notification(f"Found {len(fields)} fields on project.task", "success")
        
        # Group fields by type for better display
        field_types = {}
        for field_name, field_info in fields.items():
            field_type = field_info.get('type', 'unknown')
            if field_type not in field_types:
                field_types[field_type] = []
            field_types[field_type].append((field_name, field_info))
        
        # Display fields by type
        for field_type, type_fields in field_types.items():
            with st.expander(f"{field_type.upper()} Fields ({len(type_fields)})"):
                for field_name, field_info in sorted(type_fields, key=lambda x: x[0]):
                    # Format the display of field information
                    field_label = field_info.get('string', 'No Label')
                    required = field_info.get('required', False)
                    relation = field_info.get('relation', 'None')
                    
                    # Highlight studio fields
                    if field_name.startswith('x_'):
                        st.markdown(f"**Field**: `{field_name}` - **Label**: {field_label}")
                        st.markdown(f"**Required**: {required} - **Relation**: {relation}")
                        st.markdown("---")
                    else:
                        st.markdown(f"Field: `{field_name}` - Label: {field_label}")
                        st.markdown(f"Required: {required} - Relation: {relation}")
                        st.markdown("---")
    
    except Exception as e:
        create_notification(f"Error fetching field information: {str(e)}", "error")
        logger.error(f"Error in debug_task_fields: {e}", exc_info=True)

def company_selection_page():
    inject_enhanced_css()
    create_animated_header("Select Company", "Choose your company to begin")  # Add subtitle
    

    # Progress bar
    create_progress_steps(
        current_step=1,
        total_steps=4,
        step_labels=["Company", "Sales Order", "Parent Task", "Subtasks"]
    )
    # Connect to Odoo
    if "odoo_uid" not in st.session_state or "odoo_models" not in st.session_state:
        with st.spinner("Connecting to Odoo..."):
            uid, models = authenticate_odoo()
            if uid and models:
                st.session_state.odoo_uid = uid
                st.session_state.odoo_models = models
            else:
                create_notification("Failed to connect to Odoo. Please check your credentials.", "error")
                return
    else:
        uid = st.session_state.odoo_uid
        models = st.session_state.odoo_models

    # Fetch companies if not already in session
    if "companies" not in st.session_state:
        with st.spinner("Fetching companies..."):
            companies = get_companies(models, uid)
            if companies:
                st.session_state.companies = companies
            else:
                create_notification("No companies found or error fetching companies.", "warning")
                st.session_state.companies = []

    # Create form for company selection
    style_form_container()
    with st.form("company_selection_form"):
        st.subheader("Select Company")
        
        company_options = st.session_state.companies
        selected_company = st.selectbox(
            "Company",
            company_options
        )

        submit = st.form_submit_button("Next")
        
        if submit:
            # Validate selection
            if not selected_company:
                create_notification("Please select a company.", "error")
                return
                
            # Save to session state
            st.session_state.selected_company = selected_company
            st.session_state.company_selection_done = True
            
            create_notification(f"Selected company: {selected_company}", "success")
            st.rerun()

def email_analysis_page():
    inject_enhanced_css()    
    create_animated_header("Email Analysis", "Extract information from recent emails")
    
    # Progress bar
    create_progress_steps(
        current_step=3,
        total_steps=5,
        step_labels=["Company", "Sales Order", "Email Analysis", "Parent Task", "Subtasks"]
    )
        
    # Navigation
    # Navigation
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("← Back"):
            # Go back to sales order page
            st.session_state.pop("adhoc_sales_order_done", None)
            st.session_state.pop("email_analysis_done", None)
            st.session_state.pop("email_analysis_skipped", None)
            st.session_state.pop("email_analysis", None)
            st.rerun()

    # Get variables first (these are used in the form below)
    selected_company = st.session_state.get("selected_company", "")
    parent_sales_order_item = st.session_state.get("parent_sales_order_item", "")
    customer = st.session_state.get("customer", "")
    project = st.session_state.get("project", "")

    # Display current selection
    def display_current_selection():
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**Company:** {selected_company}")
        with col2:
            st.markdown(f"**Sales Order:** {parent_sales_order_item}")
        with col3:
            st.markdown(f"**Customer:** {customer}")
        with col4:
            st.markdown(f"**Project:** {project}")

    create_glass_card(content=display_current_selection, title="Current Selection", icon="📋")
    
    # Suggested search terms OUTSIDE the form
    if parent_sales_order_item or customer:
        st.write("Suggested search terms:")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if parent_sales_order_item and st.button(f"Order: {parent_sales_order_item}", key="so_btn"):
                st.session_state.search_query = parent_sales_order_item
                st.rerun()
        with col2:
            if customer and st.button(f"Customer: {customer}", key="cust_btn"):
                st.session_state.search_query = customer
                st.rerun()
        with col3:
            if st.button("Recent emails", key="recent_btn"):
                st.session_state.search_query = ""
                st.rerun()
    
    # SKIP OPTION - always available outside any form
    if st.button("Skip Email Analysis", key="skip_outside"):
        st.session_state.email_analysis_done = True
        st.session_state.email_analysis_skipped = True
        st.rerun()
    
    # Check for Gmail authentication status BEFORE any forms
    gmail_authenticated = "google_gmail_creds" in st.session_state
    
    if not gmail_authenticated:
        # Authentication UI - completely outside of any form
        create_notification("### Google Authentication Required", "info")
        st.markdown("[Click here to authenticate with Google Gmail](https://prezlab-tms.streamlit.app/)")
        create_notification("You need to authenticate with Gmail before analyzing emails", "warning")
        return  # Exit the function early - don't show any forms
    
    # Only proceed with email fetching if already authenticated
    # Email Analysis Options Form
    style_form_container()
    with st.form("email_analysis_options"):
        st.subheader("Email Analysis Options")
        
        # Checkbox to enable/disable email analysis
        use_email_analysis = st.checkbox("Use Email Analysis to Enhance Task Details", value=True)
        
        # Group emails checkbox
        show_threads = st.checkbox("Group emails by conversation thread", value=True)
        
        if use_email_analysis:
            # Free text search - use session state value if set
            default_search = st.session_state.get("search_query", "")
            search_query = st.text_input("Search for emails (subject, sender, or content):",
                               value=default_search,
                               help="Type any keywords to find relevant emails")
            
            # Number of emails to fetch
            email_limit = st.slider("Number of emails to fetch", min_value=5, max_value=100, value=50)
        
        # Form submit button
        fetch_emails = st.form_submit_button("Fetch Emails")
    
    # Handle form submission OUTSIDE the form
    if fetch_emails and use_email_analysis:
        with st.spinner("Connecting to Gmail..."):
            try:
                # Gmail service initialization now happens outside any form
                gmail_service = get_gmail_service()
                
                if gmail_service:
                    with st.spinner(f"Fetching up to {email_limit} emails..."):
                        recent_emails = fetch_recent_emails(gmail_service, total_emails=email_limit, query=search_query)
                        
                        if show_threads:
                            from gmail_integration import extract_email_threads
                            threads = extract_email_threads(recent_emails)
                            st.session_state.email_threads = threads
                        
                        st.session_state.recent_emails = recent_emails
                        st.session_state.show_threads = show_threads
                        st.rerun()  # Refresh to show results
                else:
                    create_notification("Failed to connect to Gmail. Please check your credentials.", "error")
            except Exception as e:
                create_notification(f"Error connecting to Gmail: {str(e)}", "error")
    
    # Display emails or threads if fetched
    if "recent_emails" in st.session_state:
        if st.session_state.get("show_threads", False) and "email_threads" in st.session_state:
            # Display threads
            threads = st.session_state.email_threads
            thread_count = len(threads)
            
            if thread_count > 0:
                create_notification(f"Found {thread_count} email threads", "success")
                
                # Create a searchable dropdown
                thread_options = []
                thread_ids = list(threads.keys())
                
                for thread_id in thread_ids:
                    thread_emails = threads[thread_id]
                    # Use the most recent email in thread for display
                    latest_email = thread_emails[0] if thread_emails else {"from": "Unknown", "subject": "No Subject"}
                    option_text = f"{latest_email.get('from', 'Unknown')} - {latest_email.get('subject', 'No Subject')}"
                    thread_options.append(option_text)
                
                # Free text search for threads
                thread_search = st.text_input("Search within found threads:", 
                                     help="Type to filter the thread list below")
                
                # Filter the thread options based on search
                filtered_thread_options = []
                filtered_thread_indices = []
                
                for i, option in enumerate(thread_options):
                    if not thread_search or thread_search.lower() in option.lower():
                        filtered_thread_options.append(option)
                        filtered_thread_indices.append(i)
                
                if filtered_thread_options:
                    selected_option = st.selectbox(
                        "Select Thread to Analyze:",
                        options=range(len(filtered_thread_options)),
                        format_func=lambda i: filtered_thread_options[i]
                    )
                    
                    # Get the actual thread index
                    selected_thread_idx = filtered_thread_indices[selected_option]
                    selected_thread_id = thread_ids[selected_thread_idx]
                    selected_thread = threads[selected_thread_id]
                
                    # Show the thread content
                    # For threaded emails (replace the existing code)
                    with st.expander("View Thread Content", expanded=True):
                        for i, email in enumerate(selected_thread):
                            st.markdown(f"### Email {i+1}")
                            st.markdown(f"**From:** {email.get('from', 'Unknown')}")
                            st.markdown(f"**Subject:** {email.get('subject', 'No Subject')}")
                            st.markdown(f"**Date:** {email.get('date', 'Unknown')}")
                            
                            # Show email content
                            body = email.get('body', '')
                            if len(body) > 200:
                                st.markdown(f"**Content Preview:**\n{body[:200]}...")
                                # Replace nested expander with checkbox
                                show_full = st.checkbox(f"Show full content for Email {i+1}", key=f"show_full_thread_{i}")
                                if show_full:
                                    st.markdown(f"**Full Content:**\n{body}")
                            else:
                                st.markdown(f"**Content:**\n{body}")
                            
                            st.markdown("---")
                    
                    # Now create a form for analyzing - separate from thread selection
                    style_form_container()
                    with st.form("analyze_thread_form"):
                        st.subheader("Analyze Selected Thread")
                        
                        # Email selection
                        st.write("Select emails to include in analysis:")
                        include_emails = []
                        for i, email in enumerate(selected_thread):
                            include = st.checkbox(f"Include Email {i+1}", value=True, key=f"email_{i}")
                            if include:
                                include_emails.append(i)
                        
                        # This is the submit button
                        analyze_thread_button = st.form_submit_button("Analyze Selected Emails")
                    
                    # Handle analysis OUTSIDE the form
                    if analyze_thread_button:
                        if include_emails:
                            with st.spinner("Analyzing emails with AI..."):
                                # Combine emails and analyze
                                combined_text = "Combined Email Thread:\n\n"
                                for i in include_emails:
                                    email = selected_thread[i]
                                    combined_text += f"Email {i+1}:\n"
                                    combined_text += f"From: {email.get('from', 'Unknown')}\n"
                                    combined_text += f"Subject: {email.get('subject', 'No Subject')}\n"
                                    combined_text += f"Content: {email.get('body', '')}\n\n"
                                
                                # Analyze the combined text
                                analysis_results = analyze_email(combined_text)
                                
                                # Store and proceed
                                st.session_state.email_analysis = analysis_results
                                st.session_state.email_analysis_done = True
                                st.session_state.email_analysis_skipped = False
                                st.rerun()
                        else:
                            create_notification("Please select at least one email to analyze.", "warning")
                else:
                    create_notification("No threads match your search. Try different terms.", "warning")
            else:
                create_notification("No email threads found. Try different search terms.", "warning")
                
                # Button to try again - outside any form
                if st.button("Try Different Search"):
                    st.session_state.pop("recent_emails", None)
                    st.session_state.pop("email_threads", None)
                    st.rerun()
        
        # Individual emails view (not threads)
        else:
            recent_emails = st.session_state.recent_emails
            if recent_emails:
                create_notification(f"Found {len(recent_emails)} emails", "success")
                
                # Create searchable dropdown for individual emails
                email_search = st.text_input("Search within found emails:", 
                                   help="Type to filter the email list below",
                                   key="email_search_indiv")
                
                # Filter emails based on search
                filtered_emails = []
                filtered_indices = []
                for i, email in enumerate(recent_emails):
                    subject = email.get('subject', 'No Subject')
                    sender = email.get('from', 'Unknown')
                    option_text = f"{sender} - {subject}"
                    
                    if not email_search or email_search.lower() in option_text.lower():
                        filtered_emails.append(option_text)
                        filtered_indices.append(i)
                
                if filtered_emails:
                    selected_email_option = st.selectbox(
                        "Select Email to Analyze:",
                        range(len(filtered_emails)),
                        format_func=lambda i: filtered_emails[i]
                    )
                    
                    # Get actual email index
                    selected_email_idx = filtered_indices[selected_email_option]
                    selected_email = recent_emails[selected_email_idx]
                    
                    # Show the selected email
                    # For individual emails (replace the existing code)
                    with st.expander("View Email Content", expanded=True):
                        st.markdown(f"**From:** {selected_email.get('from', 'Unknown')}")
                        st.markdown(f"**Subject:** {selected_email.get('subject', 'No Subject')}")
                        st.markdown(f"**Date:** {selected_email.get('date', 'Unknown')}")
                        
                        body = selected_email.get('body', '')
                        if len(body) > 200:
                            st.markdown(f"**Content Preview:**\n{body[:200]}...")
                            # Replace nested expander with checkbox
                            show_full = st.checkbox("Show full content", key=f"show_full_email_{selected_email_idx}")
                            if show_full:
                                st.markdown(f"**Full Content:**\n{body}")
                        else:
                            st.markdown(f"**Content:**\n{body}")
                    
                    # Single email analysis button - outside forms
                    if st.button("Analyze this Email", key="analyze_single_email"):
                        with st.spinner("Analyzing email with AI..."):
                            email_text = f"Subject: {selected_email.get('subject', '')}\n\nBody: {selected_email.get('body', '')}"
                            analysis_results = analyze_email(email_text)
                            # If the result is in raw_analysis, parse it
                            if "raw_analysis" in analysis_results:
                                import json
                                raw = analysis_results["raw_analysis"].strip()
                                if raw.startswith("```json"):
                                    raw = raw[7:]
                                if raw.endswith("```"):
                                    raw = raw[:-3]
                                try:
                                    parsed = json.loads(raw)
                                    analysis_results.update(parsed)
                                except Exception as e:
                                    st.warning(f"Could not parse AI analysis: {e}")
                            # Extract and normalize client deadline date
                            if "client_deadline" in analysis_results:
                                import re
                                from datetime import datetime
                                deadline_str = analysis_results["client_deadline"]
                                match = re.search(r'(\d{1,2})(?:st|nd|rd|th)? of ([A-Za-z]+)', deadline_str)
                                if match:
                                    day = int(match.group(1))
                                    month_str = match.group(2)
                                    try:
                                        month = datetime.strptime(month_str, '%B').month
                                    except ValueError:
                                        try:
                                            month = datetime.strptime(month_str, '%b').month
                                        except ValueError:
                                            month = 7
                                    year = datetime.now().year
                                    try:
                                        client_due_date = datetime(year, month, day)
                                        analysis_results["client_due_date_formatted"] = client_due_date.strftime('%Y/%m/%d')
                                    except ValueError:
                                        # Invalid date, skip setting the formatted date
                                        pass
                                else:
                                    match = re.search(r'(\d{1,2})(?:st|nd|rd|th)? ?([A-Za-z]+)', deadline_str)
                                    if match:
                                        day = int(match.group(1))
                                        month_str = match.group(2)
                                        try:
                                            month = datetime.strptime(month_str, '%B').month
                                        except ValueError:
                                            try:
                                                month = datetime.strptime(month_str, '%b').month
                                            except ValueError:
                                                month = 7
                                        year = datetime.now().year
                                        try:
                                            client_due_date = datetime(year, month, day)
                                            analysis_results["client_due_date_formatted"] = client_due_date.strftime('%Y/%m/%d')
                                        except ValueError:
                                            # Invalid date, skip setting the formatted date
                                            pass
                            # Extract number of images for design units and set service category
                            if "services" in analysis_results:
                                match = re.search(r'(\d+)\s*AI\s*Images?', analysis_results["services"], re.IGNORECASE)
                                if match:
                                    analysis_results["design_units"] = int(match.group(1))
                                    analysis_results["service_category_1"] = "AI Image Generation"
                            # Store analysis results
                            st.session_state.email_analysis = analysis_results
                            st.session_state.email_analysis_skipped = False
                            st.rerun()
                else:
                    create_notification("No emails match your search. Try different terms.", "warning")
            else:
                create_notification("No emails found. Try different search terms.", "warning")
                
                # Button to try again - outside any form
                if st.button("Try Different Search", key="try_diff_search_indiv"):
                    st.session_state.pop("recent_emails", None)
                    st.rerun()
    
    # Display analysis results if available
    if "email_analysis" in st.session_state and not st.session_state.get("email_analysis_skipped", True):
        analysis_results = st.session_state.email_analysis
        # DEBUG: Show session state for troubleshooting
        st.markdown("---")
        st.markdown("### Debug: Session State Snapshot")
        st.write(dict(st.session_state))
        st.markdown("---")
        # New: Show a confirmation/preview form for AI suggestions
        if "email_analysis_confirmed" not in st.session_state:
            with st.form("ai_suggestion_confirmation_form"):
                st.subheader("Review and Confirm AI Suggestions")
                parent_task_title = st.text_input("Parent Task Title", value=analysis_results.get("parent_task_title", ""))
                client_deadline = st.text_input("Client Deadline", value=analysis_results.get("client_deadline", ""))
                suggested_internal_deadline = st.text_input("Suggested Internal Deadline", value=analysis_results.get("suggested_internal_deadline", ""))
                target_language = st.text_input("Target Language", value=analysis_results.get("target_language", ""))
                service_category_1 = st.text_input("Service Category 1", value=analysis_results.get("service_category_1", ""))
                service_category_2 = st.text_input("Service Category 2", value=analysis_results.get("service_category_2", ""))
                design_units = st.text_input("Design Units", value=analysis_results.get("design_units", ""))
                requirements = st.text_area("Special Requirements", value=analysis_results.get("requirements", ""))
                urgency = st.text_input("Urgency", value=analysis_results.get("urgency", ""))
                # Subtask suggestions as editable list
                subtask_suggestions = analysis_results.get("subtask_suggestions", [])
                st.markdown("**Subtask Suggestions:**")
                edited_subtasks = []
                for i, sub in enumerate(subtask_suggestions):
                    edited = st.text_input(f"Subtask {i+1}", value=sub, key=f"ai_subtask_{i}")
                    edited_subtasks.append(edited)
                # Add ability to add/remove subtasks
                new_subtask = st.text_input("Add New Subtask", value="", key="ai_new_subtask")
                if new_subtask:
                    edited_subtasks.append(new_subtask)
                confirm = st.form_submit_button("Confirm and Use These Suggestions")
                if confirm:
                    # Store confirmed values in session_state for use in parent/subtask forms
                    st.session_state.email_analysis_confirmed = {
                        "parent_task_title": parent_task_title,
                        "client_deadline": client_deadline,
                        "suggested_internal_deadline": suggested_internal_deadline,
                        "target_language": target_language,
                        "service_category_1": service_category_1,
                        "service_category_2": service_category_2,
                        "design_units": design_units,
                        "requirements": requirements,
                        "urgency": urgency,
                        "subtask_suggestions": [s for s in edited_subtasks if s.strip()]
                    }
                    st.session_state.email_analysis = {**analysis_results, **st.session_state.email_analysis_confirmed}
                    st.session_state.email_analysis_done = True
                    st.session_state.email_analysis_skipped = False
                    st.rerun()
        else:
            # Already confirmed, show summary and continue button
            def display_analysis_summary():
                confirmed = st.session_state.email_analysis_confirmed
                for key, value in confirmed.items():
                    if key == "subtask_suggestions":
                        st.markdown("**Subtask Suggestions:**")
                        for i, sub in enumerate(value):
                            st.markdown(f"{i+1}. {sub}")
                    else:
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
            create_glass_card(content=display_analysis_summary, title="Confirmed Email Analysis", icon="📧")
            if st.button("Continue to Parent Task Details", type="primary"):
                st.rerun()

def google_auth_page():
    st.title("Google Services Authentication")
    
    # Check for both credential presence and backup flags
    gmail_authenticated = "google_gmail_creds" in st.session_state
    drive_authenticated = "google_drive_creds" in st.session_state
    
    # Check for backup auth completion flags
    gmail_auth_complete = st.session_state.get("gmail_auth_complete", False)
    drive_auth_complete = st.session_state.get("drive_auth_complete", False)
    
    # Add debug info to help troubleshoot
    with st.sidebar.expander("Debug Info", expanded=False):
        st.write("Session State Keys:", list(st.session_state.keys()))
        st.write("Gmail Creds:", gmail_authenticated)
        st.write("Drive Creds:", drive_authenticated)
        st.write("Gmail Auth Complete Flag:", gmail_auth_complete)
        st.write("Drive Auth Complete Flag:", drive_auth_complete)
        
        # Add a reset button
        if st.button("Reset Google Auth Status (Debug)"):
            keys_to_remove = [
                'google_auth_complete', 
                'google_gmail_creds', 
                'google_drive_creds',
                'gmail_auth_complete', 
                'drive_auth_complete'
            ]
            for key in keys_to_remove:
                if key in st.session_state:
                    st.session_state.pop(key, None)
            st.rerun()
    
    create_notification("Please authenticate with Google to enable Gmail and Drive functionality.", "info")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Gmail")
        if gmail_authenticated or gmail_auth_complete:
            create_notification("✅ Authenticated", "success")
        else:
            create_notification("⚠️ Not authenticated", "warning")
            if st.button("Authenticate Gmail"):
                with st.spinner("Connecting to Gmail..."):
                    gmail_service = get_gmail_service()
                    if gmail_service:
                        # Set both the credential and backup flags
                        st.session_state.gmail_auth_complete = True
                        create_notification("Gmail authentication successful!", "success")
                        st.rerun()
    
    with col2:
        st.subheader("Google Drive")
        if drive_authenticated or drive_auth_complete:
            create_notification("✅ Authenticated", "success")
        else:
            create_notification("⚠️ Not authenticated", "warning")
            if st.button("Authenticate Drive"):
                with st.spinner("Connecting to Drive..."):
                    drive_service = get_drive_service()
                    if drive_service:
                        # Set both the credential and backup flags
                        st.session_state.drive_auth_complete = True
                        create_notification("Drive authentication successful!", "success")
                        st.rerun()
    
    # Check if both services are authenticated
    if (gmail_authenticated or gmail_auth_complete) and (drive_authenticated or drive_auth_complete):
        create_notification("All services authenticated! You're ready to proceed.", "success")
        
        # Set the main flag that the main() function checks
        st.session_state.google_auth_complete = True
        
        if st.button("Continue to Dashboard", type="primary"):
            # Ensure the flag is set before continuing
            st.session_state.google_auth_complete = True
            st.rerun()
    else:
        # Make sure google_auth_complete stays False until both services are authenticated
        st.session_state.google_auth_complete = False

def initialize_gmail_connection():
    """
    Initialize connection to Gmail API and handle authentication.
    Returns the Gmail service object or None if connection fails.
    """
    try:
        service = get_gmail_service()
        if service:
            return service
        else:
            create_notification("Failed to initialize Gmail service. Check your credentials.", "error")
            return None
    except Exception as e:
        create_notification(f"Error connecting to Gmail: {str(e)}", "error")
        return None
    
def designer_selection_page():
    """
    Enhanced Designer Selection & Booking page with modern UI
    """
    inject_enhanced_css()
    
    # Add custom CSS for designer cards
    designer_css = f"""
    <style>
    .designer-card {{
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }}
    
    .designer-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }}
    
    .designer-card.selected {{
        border: 2px solid {COLORS['primary_purple']};
        background: linear-gradient(to right, {COLORS['primary_purple']}05, transparent);
    }}
    
    .designer-avatar {{
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, {COLORS['primary_purple']}, {COLORS['coral']});
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(128, 90, 249, 0.3);
    }}
    
    .match-indicator {{
        position: absolute;
        top: 1rem;
        right: 1rem;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: white;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.2rem;
    }}
    
    .skills-tag {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        background: {COLORS['light_purple']};
        color: {COLORS['primary_purple']};
        border-radius: 20px;
        font-size: 0.875rem;
        margin: 0.25rem;
    }}
    
    .task-preview {{
        background: linear-gradient(135deg, {COLORS['light_purple']}, {COLORS['light_gray']});
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid {COLORS['primary_purple']};
    }}
    
    @keyframes bounce {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-20px); }}
    }}
    
    @keyframes scaleIn {{
        0% {{ transform: scale(0); opacity: 0; }}
        100% {{ transform: scale(1); opacity: 1; }}
    }}
    
    .success-animation {{
        animation: bounce 1s infinite;
    }}
    </style>
    """
    st.markdown(designer_css, unsafe_allow_html=True)
    
    create_animated_header("Designer Selection & Booking", "AI-Powered Designer Matching")
    
    # Check if we have tasks
    if "created_tasks" not in st.session_state or not st.session_state.created_tasks:
        create_notification("No tasks available for designer assignment.", "warning")
        if st.button("Return to Home", type="primary"):
            for key in ["form_type", "company_selection_done", "designer_selection", 
                      "created_tasks", "parent_task_id"]:
                st.session_state.pop(key, None)
            st.rerun()
        return
    
    # Get connection
    uid = st.session_state.odoo_uid
    models = st.session_state.odoo_models
    
    # Get Odoo credentials for constants
    odoo_credentials = st.session_state.get('odoo_credentials', {})
    ODOO_DB = odoo_credentials.get('db')
    ODOO_PASSWORD = odoo_credentials.get('password')
    
    # Load designers and employees
    with st.spinner("Loading designer information..."):
        try:
            designers_df = load_designers()
            if designers_df.empty:
                create_notification("No designer information available.", "error")
                return
            employees = get_all_employees_in_planning(models, uid)
        except Exception as e:
            create_notification(f"Error loading designers: {str(e)}", "error")
            logger.error(f"Error loading designers: {e}", exc_info=True)
            return
    
    # Parent task summary with enhanced design
    if st.session_state.get("parent_task_id"):
        parent_task_id = st.session_state.parent_task_id
        
        # Create parent task summary card
        def display_parent_summary():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                parent_title = st.session_state.get('adhoc_parent_task_title') or st.session_state.get('retainer_parent_task_title', 'Parent Task')
                st.markdown(f"### 📋 {parent_title}")
                st.markdown(f"**ID:** {parent_task_id} | **Company:** {st.session_state.get('selected_company', '')}")
            with col2:
                st.markdown(f"**Project:** {st.session_state.get('project', '')}")
                st.markdown(f"**Customer:** {st.session_state.get('customer', '')}")
            with col3:
                if "drive_folder_link" in st.session_state:
                    st.markdown(f"[📁 Open Drive Folder]({st.session_state.drive_folder_link})")
        
        create_glass_card(content=display_parent_summary, title="Project Overview", icon="🎯")
    
    # Task Progress Overview
    tasks = st.session_state.created_tasks
    total_tasks = len(tasks)
    assigned_tasks = sum(1 for task in tasks if task.get("designer_assigned"))
    
    # Progress metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        create_metric_card("Total Tasks", str(int(total_tasks)), icon="📊")
    with col2:
        create_metric_card("Assigned", str(int(assigned_tasks)), icon="✅")
    with col3:
        remaining = int(total_tasks) - int(assigned_tasks)
        create_metric_card("Remaining", str(remaining), icon="⏳")
    
    # Progress bar
    progress = (assigned_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    progress_html = f"""
    <div style="margin: 2rem 0;">
        <div style="width: 100%; background-color: {COLORS['light_gray']}; 
                    border-radius: 10px; overflow: hidden;">
            <div style="width: {progress}%; background: linear-gradient(90deg, 
                       {COLORS['primary_purple']}, {COLORS['coral']}); 
                       height: 10px; transition: width 0.5s ease;">
            </div>
        </div>
        <p style="text-align: center; margin-top: 0.5rem; color: {COLORS['dark_gray']};">
            {progress:.0f}% Complete
        </p>
    </div>
    """
    st.markdown(progress_html, unsafe_allow_html=True)
    
    # Process each task
    for i, task in enumerate(tasks):
        # Task section with enhanced design
        task_name = task.get('name', f'Task ID: {task.get("id", "Unknown")}')
        task_id = task.get('id')
        
        # Task header with status
        if task.get("designer_assigned"):
            status_html = f"""
            <div style="display: flex; justify-content: space-between; align-items: center; 
                        margin-bottom: 1rem;">
                <h3 style="margin: 0; color: {COLORS['navy']};">Task {i+1}: {task_name}</h3>
                <span class="status-pill status-completed" style="
                    background: {COLORS['success']}20;
                    color: {COLORS['success']};
                    padding: 0.5rem 1rem;
                    border-radius: 50px;
                    font-weight: 600;
                ">
                    ✅ Assigned to {task['designer_assigned']}
                </span>
            </div>
            """
        else:
            status_html = f"""
            <div style="display: flex; justify-content: space-between; align-items: center; 
                        margin-bottom: 1rem;">
                <h3 style="margin: 0; color: {COLORS['navy']};">Task {i+1}: {task_name}</h3>
                <span class="status-pill status-pending" style="
                    background: {COLORS['warning']}20;
                    color: {COLORS['warning']};
                    padding: 0.5rem 1rem;
                    border-radius: 50px;
                    font-weight: 600;
                ">
                    ⏳ Pending Assignment
                </span>
            </div>
            """
        st.markdown(status_html, unsafe_allow_html=True)
        
        # Task details preview
        with st.container():
            # Get service category names
            service_cat_1 = "Not specified"
            if task.get('x_studio_service_category_1'):
                if isinstance(task['x_studio_service_category_1'], list) and len(task['x_studio_service_category_1']) >= 2:
                    service_cat_1 = task['x_studio_service_category_1'][1]
                else:
                    service_cat_1 = str(task['x_studio_service_category_1'])
            
            task_preview_html = f"""
            <div class="task-preview">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    <div>
                        <strong>Service Category:</strong><br>
                        {service_cat_1}
                    </div>
                    <div>
                        <strong>Target Language:</strong><br>
                        {task.get('x_studio_target_language', 'Not specified')}
                    </div>
                    <div>
                        <strong>Due Date:</strong><br>
                        {task.get('x_studio_client_due_date_3', 'Not set')}
                    </div>
                </div>
            </div>
            """
            st.markdown(task_preview_html, unsafe_allow_html=True)
        
        # Only show designer selection if not assigned
        if not task.get("designer_assigned"):
            # Action buttons
            col1 = st.container()
            with col1:
                if st.button(f"🤖 Find Best Designers", key=f"suggest_{task_id}", use_container_width=True, type="primary"):
                    with st.spinner("AI analyzing designer skills..."):
                        # Get task details for matching
                        task_details = f"""
                        Task: {task_name}
                        Service Category: {service_cat_1}
                        Target Language: {task.get('x_studio_target_language', '')}
                        Project: {st.session_state.get('project', '')}
                        Customer: {st.session_state.get('customer', '')}
                        Description: {task.get('description', '')}
                        """
                        
                        # Calculate due date and duration
                        due_date = None
                        if 'x_studio_client_due_date_3' in task and task['x_studio_client_due_date_3']:
                            try:
                                if isinstance(task['x_studio_client_due_date_3'], str):
                                    due_date = pd.to_datetime(task['x_studio_client_due_date_3'])
                                else:
                                    due_date = task['x_studio_client_due_date_3']
                            except:
                                due_date = datetime.now() + pd.Timedelta(days=7)
                        else:
                            due_date = datetime.now() + pd.Timedelta(days=7)
                            
                        # Estimate task duration based on design units
                        estimated_duration = 8  # Default hours
                        design_units_sc1 = task.get('x_studio_total_no_of_design_units_sc1', 0) or 0
                        design_units_sc2 = task.get('x_studio_total_no_of_design_units_sc2', 0) or 0
                        total_units = design_units_sc1 + design_units_sc2
                        if total_units > 0:
                            estimated_duration = max(4, total_units * 2)
                        
                        # Get ranked designers
                        ranked_designers = rank_designers_by_skill_match(task_details, designers_df)
                        
                        # Filter by availability
                        available_designers, unavailable_designers = filter_designers_by_availability(
                            ranked_designers, models, uid, due_date, estimated_duration
                        )
                        
                        # Store results
                        task_key = f"designer_options_{task_id}"
                        st.session_state[task_key] = {
                            'available': available_designers,
                            'unavailable': unavailable_designers,
                            'task_details': task_details,
                            'due_date': due_date,
                            'duration': estimated_duration
                        }
                        st.rerun()
            
            # Display designer options if available
            designer_key = f"designer_options_{task_id}"
            if designer_key in st.session_state:
                options = st.session_state[designer_key]
                available_df = options['available']
                unavailable_df = options['unavailable']
                
                # Check for reshuffling opportunities
                reshuffling_suggestion = suggest_reshuffling(
                    available_df, 
                    unavailable_df,
                    options['due_date'],
                    options['duration']
                )
                
                if reshuffling_suggestion:
                    st.markdown("### 🔄 Task Reshuffling Opportunity")
                    st.markdown(f"""
                    **Better Match Available!**  
                    Designer {reshuffling_suggestion['designer_name']} has a {reshuffling_suggestion['match_score']:.0f}% match score 
                    (vs best available: {reshuffling_suggestion['best_available_score']:.0f}%)
                    
                    **Current Schedule:**
                    - Currently working on: {reshuffling_suggestion['blocking_task_name']}
                    - Their task deadline: {reshuffling_suggestion['blocking_task_deadline']}
                    - Your task deadline: {reshuffling_suggestion['current_task_deadline']}
                    
                    **Suggestion:**  
                    Consider reshuffling tasks to assign this designer to your task, as they are a better match.
                    Their current task can be rescheduled since it has a later deadline.
                    """)
                    
                    if st.button("🔄 Proceed with Reshuffling", key=f"reshuffle_{task_id}"):
                        st.session_state[f"reshuffle_{task_id}"] = reshuffling_suggestion
                        st.rerun()
                
                if not available_df.empty:
                    st.markdown("### 🎯 Recommended Designers")
                    
                    # Show top 5 available designers
                    for idx, designer in available_df.head(5).iterrows():
                        # Get designer details
                        name = designer['Name']
                        score = designer.get('match_score', 0)
                        position = designer.get('Position', 'Designer')
                        tools = designer.get('Tools', '')
                        languages = designer.get('Languages', '')
                        
                        # Availability info
                        avail_from = designer.get('available_from', '')
                        if avail_from and isinstance(avail_from, pd.Timestamp):
                            avail_str = avail_from.strftime("%b %d, %H:%M")
                        else:
                            avail_str = "Available Now"
                        
                        # Create designer card using columns
                        with st.container():
                            # Card container with custom styling
                            card_col1, card_col2, card_col3 = st.columns([1, 4, 1])
                            
                            with card_col1:
                                # Avatar
                                st.markdown(
                                    f"""
                                    <div style="
                                        width: 60px;
                                        height: 60px;
                                        border-radius: 50%;
                                        background: linear-gradient(135deg, {COLORS['primary_purple']}, {COLORS['coral']});
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        color: white;
                                        font-size: 1.5rem;
                                        font-weight: 700;
                                        box-shadow: 0 4px 15px rgba(128, 90, 249, 0.3);
                                        margin: auto;
                                    ">{name[0].upper()}</div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            
                            with card_col2:
                                # Designer info
                                st.markdown(f"**{name}**")
                                st.caption(position)
                                
                                # Status badges
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.success(f"📅 {avail_str}")
                                with col_b:
                                    if languages:
                                        st.info(f"🌐 {languages[:20]}{'...' if len(languages) > 20 else ''}")
                                
                                # Skills
                                if tools:
                                    tool_list = [t.strip() for t in tools.split(',')[:3] if t.strip()]
                                    skills_html = " ".join([f'<span style="background: {COLORS["light_purple"]}; color: {COLORS["primary_purple"]}; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.875rem; margin: 0.25rem; display: inline-block;">{tool}</span>' for tool in tool_list])
                                    st.markdown(skills_html, unsafe_allow_html=True)
                            
                            with card_col3:
                                # Match score
                                if score >= 80:
                                    score_color = COLORS['success']
                                elif score >= 60:
                                    score_color = COLORS['warning']
                                else:
                                    score_color = COLORS['danger']
                                
                                st.markdown(
                                    f"""
                                    <div style="
                                        width: 60px;
                                        height: 60px;
                                        border-radius: 50%;
                                        background: white;
                                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        font-weight: 700;
                                        font-size: 1.2rem;
                                        color: {score_color};
                                        margin: auto;
                                    ">{score:.0f}%</div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            
                            # Select button
                            if st.button(f"Select {name}", key=f"select_{task_id}_{idx}", 
                                    use_container_width=True, type="primary"):
                                st.session_state[f"selected_designer_{task_id}"] = name
                                st.session_state[f"schedule_task_{task_id}"] = True
                                st.rerun()
                            
                            # Add spacing between cards
                            st.markdown("<br>", unsafe_allow_html=True)
                else:
                    create_notification("No designers available for this task's timeline.", "warning")
                    
                    # Show unavailable designers as alternatives
                    if not unavailable_df.empty:
                        st.markdown("### 🔍 Best Matches (Currently Unavailable)")
                        for _, designer in unavailable_df.head(3).iterrows():
                            st.markdown(f"**{designer['Name']}** - Match: {designer.get('match_score', 0):.0f}%")
        
        st.markdown("---")
    
    # Final actions
    if assigned_tasks == total_tasks:
        # Success animation
        success_html = f"""
        <div style="text-align: center; margin: 2rem 0;">
            <div style="font-size: 4rem;" class="success-animation">🎉</div>
            <h2 style="color: {COLORS['primary_purple']};">All Tasks Assigned!</h2>
            <p style="color: {COLORS['dark_gray']};">Great job! All tasks have been assigned to designers.</p>
        </div>
        """
        st.markdown(success_html, unsafe_allow_html=True)
        
        if st.button("🏁 Complete Process", type="primary", use_container_width=True):
            # Clear session state
            keys_to_clear = [
                "form_type", "adhoc_sales_order_done", "adhoc_parent_input_done",
                "retainer_parent_input_done", "subtask_index", "created_tasks",
                "designer_selection", "parent_task_id", "company_selection_done",
                "email_analysis_done", "email_analysis_skipped"
            ]
            for key in keys_to_clear:
                st.session_state.pop(key, None)
            st.rerun()
    else:
        # Option to skip remaining assignments
        if st.button("Complete Process (Skip Remaining)", use_container_width=True):
            for key in ["form_type", "company_selection_done", "designer_selection", 
                      "created_tasks", "parent_task_id"]:
                st.session_state.pop(key, None)
            st.rerun()
    
    # Handle scheduling in the background
    for task in tasks:
        if f"schedule_task_{task['id']}" in st.session_state and st.session_state[f"schedule_task_{task['id']}"]:
            selected_designer_key = f"selected_designer_{task['id']}"
            
            if selected_designer_key in st.session_state:
                designer_name = st.session_state[selected_designer_key]
                
                # Get designer details
                designer_key = f"designer_options_{task['id']}"
                if designer_key in st.session_state:
                    options = st.session_state[designer_key]
                    available_df = options['available']
                    
                    designer_row = available_df[available_df['Name'] == designer_name]
                    if not designer_row.empty:
                        # Schedule the task
                        with st.spinner(f"Booking {designer_name} for the task..."):
                            # Find employee ID
                            employee_id = find_employee_id(designer_name, employees)
                            
                            if employee_id:
                                # Get availability
                                available_from = designer_row.iloc[0].get('available_from')
                                available_until = designer_row.iloc[0].get('available_until')
                                
                                # Get task name with context
                                task_name = task.get('name', f"Task {task['id']}")
                                project_name = st.session_state.get('project', '')
                                customer_name = st.session_state.get('customer', '')
                                
                                planning_task_name = f"{task_name}"
                                if parent_task_id:
                                    planning_task_name += f" | Parent ID: {parent_task_id}"
                                if project_name:
                                    planning_task_name += f" | {project_name}"
                                if customer_name:
                                    planning_task_name += f" | {customer_name}"
                                
                                # Convert timestamps
                                task_start = available_from
                                task_end = available_until
                                
                                if isinstance(task_start, pd.Timestamp):
                                    task_start = task_start.to_pydatetime()
                                if isinstance(task_end, pd.Timestamp):
                                    task_end = task_end.to_pydatetime()
                                
                                # Create planning slot
                                slot_id = create_task(
                                    models, uid, employee_id, 
                                    planning_task_name, 
                                    task_start, task_end,
                                    parent_task_id=parent_task_id,
                                    task_id=task['id']
                                )
                                
                                if slot_id:
                                    # Update task with designer
                                    assignment_note = (
                                        f"\n\n--- Designer Assignment ---\n"
                                        f"Designer: {designer_name}\n"
                                        f"Assigned: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                                        f"Scheduled: {task_start.strftime('%Y-%m-%d %H:%M')} to {task_end.strftime('%Y-%m-%d %H:%M')}\n"
                                        f"Planning Slot ID: {slot_id}\n"
                                        f"Match Score: {designer_row.iloc[0].get('match_score', 0):.0f}%"
                                    )
                                    
                                    success = update_task_designer(
                                        models, uid, task['id'], designer_name,
                                        assignment_note=assignment_note,
                                        planning_slot_id=slot_id,
                                        role="Designer"
                                    )
                                    
                                    if success:
                                        create_notification(f"✅ Successfully assigned {designer_name} to the task!", "success")
                                        task["designer_assigned"] = designer_name
                                        task["planning_slot_id"] = slot_id
                                    else:
                                        create_notification(f"Task scheduled but couldn't update task details. Check Odoo.", "warning")
                                    
                                    # Clean up session state
                                    st.session_state.pop(f"schedule_task_{task['id']}", None)
                                    st.session_state.pop(f"selected_designer_{task['id']}", None)
                                    st.rerun()
                                else:
                                    create_notification(f"Failed to create planning slot for {designer_name}.", "error")
                            else:
                                create_notification(f"Could not find {designer_name} in the planning system.", "error")
                    else:
                        create_notification(f"Designer {designer_name} is no longer available.", "error")
            else:
                create_notification("Please select a designer first.", "warning")
                st.session_state.pop(f"schedule_task_{task['id']}", None)

# -------------------------------
# MAIN
# -------------------------------

def main():
    """
    Entry‑point for the Streamlit Task‑Management app.
    ‑   Ensures the user is logged‑in *before* we complete any Google OAuth
    ‑   Persists OAuth codes that arrive early, then processes them post‑login
    """
    from session_manager import SessionManager
    SessionManager.initialize_session()

    import streamlit as st

    inject_custom_css()
    inject_enhanced_css()


    # Set logo position based on login status
    if st.session_state.get("logged_in", False):
        # For logged-in pages, use top-right position
        add_logo(position="top-right", width=120)
    else:
        # For login page, this will be handled in login_page()
        pass
    # ------------------------------------------------------------------
    # 1)  Capture *early* Google OAuth callback codes
    # ------------------------------------------------------------------
    if "code" in st.query_params:
        # Stash it until the user finishes the TMS login
        st.session_state.pending_oauth_code = st.query_params["code"]
        st.query_params.clear()               # keeps the URL tidy

    # ------------------------------------------------------------------
    # 2)  Admin "system debug" shortcut (unchanged)
    # ------------------------------------------------------------------
    if inject_debug_page():                   # noqa: F821  (defined earlier in app.py)
        return

    # ------------------------------------------------------------------
    # 3)  Sidebar is always visible
    # ------------------------------------------------------------------
    render_sidebar()                          # noqa: F821

    # Small live‑state panel
    st.sidebar.write("Debug Info:")
    st.sidebar.write(f"Logged in: {st.session_state.get('logged_in', False)}")
    st.sidebar.write(f"Google Auth Complete: {st.session_state.get('google_auth_complete', False)}")
    st.sidebar.write(f"Google Gmail Creds: {'google_gmail_creds' in st.session_state}")
    st.sidebar.write(f"Google Drive Creds: {'google_drive_creds' in st.session_state}")

    # ------------------------------------------------------------------
    # 4)  Login gate
    # ------------------------------------------------------------------
    if not st.session_state.get("logged_in", False):
        login_page()                          # noqa: F821
        return

    # ------------------------------------------------------------------
    # 5)  *After* successful login, finish any pending OAuth handshake
    # ------------------------------------------------------------------
    if "pending_oauth_code" in st.session_state:
        code = st.session_state.pop("pending_oauth_code")

        from google_auth import handle_oauth_callback  # local import avoids circular refs
        create_notification("Finishing Google authentication…", "info")
        success = handle_oauth_callback(code)

        if success:
            create_notification("Google account linked – token saved to Supabase.", "success")
        else:
            create_notification("Google authentication failed. Please try again.", "error")

        st.rerun()     # refresh state / UI regardless of outcome
        return

    # ------------------------------------------------------------------
    # 6)  Optional Auth‑debug / Google‑auth pages (unchanged)
    # ------------------------------------------------------------------
    if st.session_state.get("show_google_auth", False):
        google_auth_page()                    # noqa: F821
        if st.button("Return to Main Page"):
            st.session_state.pop("show_google_auth", None)
            st.rerun()
        return
    elif st.session_state.get("debug_mode") == "auth_debug":
        auth_debug_page()                     # noqa: F821

    # Additional debug mode (task‑fields) — unchanged
    if st.session_state.get("debug_mode") == "task_fields":
        debug_task_fields()                   # noqa: F821
        if st.button("Return to Normal Mode"):
            st.session_state.pop("debug_mode")
            st.rerun()
        return

    # ------------------------------------------------------------------
    # 7)  Session‑validation & main workflow (unchanged)
    # ------------------------------------------------------------------
    if not validate_session():                # noqa: F821
        login_page()
        return
    
    if "login_in_progress" in st.session_state:
        del st.session_state["login_in_progress"]
        
    # Main content routing (identical to previous logic)
    if "form_type" not in st.session_state:
        type_selection_page()                 # noqa: F821
    else:
        # Designer‑selection page shown after tasks are created
        if st.session_state.get("designer_selection"):
            designer_selection_page()         # noqa: F821
        elif st.session_state.form_type == "Via Sales Order":
            if "adhoc_parent_input_done" in st.session_state:
                adhoc_subtask_page()
            elif "adhoc_sales_order_done" in st.session_state:
                if "email_analysis_done" in st.session_state:
                    adhoc_parent_task_page()
                else:
                    email_analysis_page()
            elif "company_selection_done" in st.session_state:
                sales_order_page()
            else:
                company_selection_page()
        elif st.session_state.form_type == "Via Project":
            if "retainer_parent_input_done" in st.session_state:
                retainer_subtask_page()       # noqa: F821
            else:
                retainer_parent_task_page()   # noqa: F821

if __name__ == "__main__":
    main()
# prezlab_ui.py
import streamlit as st
import base64
from pathlib import Path

st.set_page_config(
    page_title="Task Management",      # optional, whatever your title is
    layout="centered",                 # ← this flips on centered layout
)

# Constants
COLORS = {
    "navy": "#2B1B4C",
    "coral": "#FF6666",
    "yellow": "#FFC952",
    "purple": "#805AF9",
    "green": "#4EF4A8",
    "light_purple": "#E4E3FF",
    "light_coral": "#FFEDE9",
    "light_yellow": "#F7F1DE",
    "light_gray": "#EDEDED"
}

# Save logo as base64 string - you can generate this from your logo file
LOGO_BASE64 = "YOUR_BASE64_ENCODED_LOGO"

def inject_custom_css():
    """Inject custom CSS for consistent PrezLab styling without breaking layout."""
    css = """
    <style>
    /* CRITICAL FIX: Preserve Streamlit's layout structure */
    /* These classes control the main layout - we must be very careful with them */
    .main .block-container {
        /* control your maximum width */
        max-width: 1000px !important;   
        /* auto-margin centers the container */
        margin: 0 auto !important;      
        /* vertical breathing room */
        padding-top: 1rem !important;   
        padding-bottom: 1rem !important;
    }

    /* Ensure sidebar stays in position */
    [data-testid="stSidebar"] {
        min-width: 300px !important;
        max-width: 300px !important;
    }
    
    /* Fix sidebar content alignment */
    [data-testid="stSidebar"] > div:first-child {
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    
    /* Target any progress elements */
    progress {
        color: #2B1B4C !important;
    }
    
    /* Typography enhancements */
    h1, h2, h3, h4, h5, h6 {
        color: #2B1B4C !important;
        font-weight: 600 !important;
    }
    
    /* Button enhancements */
    .stButton button {
        border-radius: 4px !important;
        font-weight: 500 !important;
        transition: all 0.2s !important;
    }
    
    .stButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    
    /* Primary button styling */
    .stButton.primary button {
        background-color: #FF6666 !important;
        color: white !important;
    }
    
    /* Input field enhancements */
    .stTextInput input, 
    .stNumberInput input, 
    .stDateInput input,
    .stTextArea textarea {
        border-radius: 4px !important;
        border-color: #EDEDED !important;
    }
    
    .stTextInput input:focus, 
    .stNumberInput input:focus, 
    .stDateInput input:focus,
    .stTextArea textarea:focus {
        border-color: #FF6666 !important;
        box-shadow: 0 0 0 1px #FF666680 !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_logo(width=150):
    """Render the PrezLab logo."""
    st.markdown(
        f"""
        <img src="data:image/png;base64,{LOGO_BASE64}" width="{width}">
        """,
        unsafe_allow_html=True
    )

def header(title, with_logo=True, logo_width=120):
    """Render a PrezLab styled header."""
    if with_logo:
        cols = st.columns([1, 3])
        with cols[0]:
            render_logo(width=logo_width)
        with cols[1]:
            st.markdown(
                f"""
                <div class="prezlab-header">
                    <h1>{title}</h1>
                    <div class="prezlab-point"></div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            f"""
            <div class="prezlab-header">
                <h1>{title}</h1>
                <div class="prezlab-point"></div>
            </div>
            """,
            unsafe_allow_html=True
        )

def container(content_function, title=None, border_color="#EDEDED", bg_color="white"):
    """Create a styled container."""
    container_id = f"container_{abs(hash(title))}" if title else "container"
    
    # Container start
    st.markdown(
        f"""
        <div id="{container_id}" 
             style="background-color: {bg_color}; border-radius: 8px; 
                   padding: 1.5rem; border: 1px solid {border_color}; 
                   margin: 1rem 0; position: relative;">
        """, 
        unsafe_allow_html=True
    )
    
    # Optional title with point
    if title:
        st.markdown(
            f"""
            <div style="position: absolute; top: -15px; left: 20px; 
                       background-color: white; padding: 0 10px;">
                <div style="display: flex; align-items: center;">
                    <span style="font-weight: 600; color: {COLORS['navy']};">{title}</span>
                    <div style="margin-left: 5px; width: 5px; height: 5px; 
                              border-radius: 50%; background-color: {COLORS['coral']};"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Content goes here
    content_function()
    
    # Container end
    st.markdown("</div>", unsafe_allow_html=True)

def message(message_type, text):
    """Display a styled message."""
    if message_type == "success":
        color = COLORS["green"]
        icon = "✓"
    elif message_type == "error":
        color = COLORS["coral"]
        icon = "✕"
    elif message_type == "warning":
        color = COLORS["yellow"]
        icon = "!"
    else:  # info
        color = COLORS["purple"]
        icon = "i"
    
    st.markdown(
        f"""
        <div style="display: flex; padding: 1rem; border-radius: 4px; 
                  background-color: {color}20; border-left: 4px solid {color}; 
                  margin: 0.5rem 0;">
            <div style="background-color: {color}; color: white; width: 24px; 
                      height: 24px; border-radius: 50%; display: flex; 
                      justify-content: center; align-items: center; 
                      margin-right: 0.8rem;">
                {icon}
            </div>
            <div style="flex-grow: 1;">
                <p style="margin: 0; padding: 0; color: {COLORS['navy']};">{text}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def progress_steps(current_step, total_steps, labels=None):
    """Display a custom progress step indicator."""
    if labels is None:
        labels = [f"Step {i+1}" for i in range(total_steps)]
    
    # Generate the steps HTML
    steps_html = ""
    for i in range(total_steps):
        is_active = i < current_step
        is_current = i == current_step - 1
        
        # Set colors based on state
        step_color = COLORS["coral"] if is_active else COLORS["light_gray"]
        text_color = COLORS["navy"] if is_active else "#6E6E6E"
        font_weight = "600" if is_current else "400"
        
        steps_html += f"""
        <div style="flex: 1; display: flex; flex-direction: column; align-items: center;">
            <div style="width: 16px; height: 16px; border-radius: 50%; 
                      background-color: {step_color}; margin-bottom: 8px;"></div>
            <div style="text-align: center; font-size: 0.8rem; font-weight: {font_weight}; 
                      color: {text_color};">{labels[i]}</div>
        </div>
        """
    
    # Create progress bar and steps
    progress_pct = (current_step - 1) / (total_steps - 1) * 100 if total_steps > 1 else 0
    
    st.markdown(
        f"""
        <div style="margin: 2rem 0;">
            <div style="width: 100%; height: 4px; background-color: {COLORS['light_gray']}; 
                      margin-bottom: 1.5rem; position: relative;">
                <div style="width: {progress_pct}%; height: 100%; 
                          background-color: {COLORS['coral']};"></div>
            </div>
            <div style="display: flex; justify-content: space-between;">
                {steps_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def scribble(text, color=COLORS["coral"], style="underline"):
    """Add a scribble to text."""
    if style == "underline":
        st.markdown(
            f"""
            <div style="position: relative; display: inline-block;">
                <span style="position: relative; z-index: 2;">{text}</span>
                <svg style="position: absolute; bottom: -5px; left: 0; z-index: 1; width: 100%;" 
                     height="10" viewBox="0 0 100 10">
                    <path d="M0,5 C20,1 40,9 100,5" stroke="{color}" stroke-width="2" 
                          fill="none" stroke-linecap="round"/>
                </svg>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif style == "highlight":
        st.markdown(
            f"""
            <div style="position: relative; display: inline-block;">
                <div style="position: absolute; bottom: 0; left: 0; z-index: 1; 
                          width: 100%; height: 40%; background-color: {color}40;"></div>
                <span style="position: relative; z-index: 2;">{text}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

def add_logo(logo_filename="PrezLab-Logos-02.png", width=150, base64_string=None):
    """Add a logo to the top right corner of the app using a file or base64 string."""
    import base64
    import os
    
    try:
        encoded = None
        
        # If a base64 string is provided, use it directly
        if base64_string:
            # Strip prefix if it exists
            if "data:image/png;base64," in base64_string:
                base64_string = base64_string.split("data:image/png;base64,")[1]
            if "url(data:image/png;base64," in base64_string:
                base64_string = base64_string.split("url(data:image/png;base64,")[1].rstrip(")")
                
            encoded = base64_string
        else:
            # Use a file path
            from PIL import Image
            # Try multiple locations for the logo file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(current_dir, logo_filename),
                logo_filename,  # Try direct path
                os.path.join(".", logo_filename),  # Try relative to working dir
            ]
            
            logo_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    logo_path = path
                    break
            
            if logo_path:
                # Read the image file
                img = Image.open(logo_path)
                
                # Convert the image to base64
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                encoded = base64.b64encode(byte_im).decode()
            else:
                print(f"Logo file not found at any of: {possible_paths}")
                return
        
        if encoded:
            # Create a holder for the image with right alignment
            st.markdown(
                f"""
                <style>
                .logo-container {{
                    position: fixed;
                    top: 120px;
                    right: 30px;
                    z-index: 1000;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
            
            # Display the image
            st.markdown(
                f"""
                <div class="logo-container">
                    <img src="data:image/png;base64,{encoded}" width="{width}">
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Save the encoded logo for future use
            st.session_state.logo_base64 = encoded
            
    except Exception as e:
        print(f"Error displaying logo: {e}")
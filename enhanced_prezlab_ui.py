# enhanced_prezlab_ui.py
import streamlit as st
import base64
from pathlib import Path
import json
from datetime import datetime

# Enhanced Color Palette
COLORS = {
    # Primary Brand Colors
    "primary_purple": "#805AF9",
    "dark_purple": "#6B46E5",
    "light_purple": "#E4E3FF",
    
    # Secondary Colors
    "navy": "#2B1B4C",
    "coral": "#FF6666",
    "yellow": "#FFC952",
    "green": "#4EF4A8",
    "blue": "#4E9FF4",
    
    # Neutral Colors
    "white": "#FFFFFF",
    "light_gray": "#F8F9FA",
    "medium_gray": "#E9ECEF",
    "dark_gray": "#495057",
    "black": "#212529",
    
    # Status Colors
    "success": "#28A745",
    "warning": "#FFC107",
    "danger": "#DC3545",
    "info": "#17A2B8"
}

def inject_enhanced_css():
    """Inject modern, animated CSS with glassmorphism and smooth transitions"""
    css = f"""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    .stApp {{
        font-family: 'Inter', 'sans serif';
        background: linear-gradient(135deg, {COLORS['light_purple']} 0%, {COLORS['white']} 50%, {COLORS['light_gray']} 100%);
        background-attachment: fixed;
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* Animated Background Pattern */
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            radial-gradient(circle at 20% 50%, {COLORS['primary_purple']}20 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, {COLORS['coral']}20 0%, transparent 50%),
            radial-gradient(circle at 40% 20%, {COLORS['yellow']}20 0%, transparent 50%);
        z-index: -1;
        animation: float 20s ease-in-out infinite;
    }}
    
    @keyframes float {{
        0%, 100% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-20px); }}
    }}
    
    /* Glassmorphism Cards */
    .glass-card {{
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px 0 rgba(128, 90, 249, 0.1);
        padding: 2rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }}
    
    .glass-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 40px 0 rgba(128, 90, 249, 0.2);
    }}
    
    /* Interactive Buttons */
    .stButton > button {{
        background: linear-gradient(135deg, {COLORS['primary_purple']} 0%, {COLORS['dark_purple']} 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 50px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px 0 rgba(128, 90, 249, 0.3);
        position: relative;
        overflow: hidden;
    }}
    
    .stButton > button::before {{
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s;
    }}
    
    .stButton > button:hover::before {{
        left: 100%;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px 0 rgba(128, 90, 249, 0.4);
    }}
    
    /* Secondary Button Style */
    .secondary-button > button {{
        background: transparent;
        color: {COLORS['primary_purple']};
        border: 2px solid {COLORS['primary_purple']};
        padding: 0.75rem 2rem;
        border-radius: 50px;
        font-weight: 600;
        transition: all 0.3s ease;
    }}
    
    .secondary-button > button:hover {{
        background: {COLORS['primary_purple']};
        color: white;
        transform: translateY(-2px);
    }}
    
    /* Enhanced Input Fields */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stTextArea > div > div > textarea {{
        background: rgba(255, 255, 255, 0.9);
        border: 2px solid {COLORS['light_purple']};
        border-radius: 12px;
        padding: 0.75rem 1rem;
        transition: all 0.3s ease;
        font-family: 'Inter', 'sans serif';
    }}
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {COLORS['primary_purple']};
        box-shadow: 0 0 0 3px {COLORS['primary_purple']}20;
        outline: none;
    }}
    
    /* Animated Progress Bar */
    .progress-container {{
        background: {COLORS['light_gray']};
        border-radius: 50px;
        padding: 4px;
        margin: 2rem 0;
    }}
    
    .progress-bar {{
        background: linear-gradient(90deg, {COLORS['primary_purple']}, {COLORS['coral']});
        height: 8px;
        border-radius: 50px;
        transition: width 0.5s ease;
        position: relative;
        overflow: hidden;
    }}
    
    .progress-bar::after {{
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.3),
            transparent
        );
        animation: shimmer 2s infinite;
    }}
    
    @keyframes shimmer {{
        0% {{ transform: translateX(-100%); }}
        100% {{ transform: translateX(100%); }}
    }}
    
    /* Floating Action Button */
    .fab {{
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        width: 60px;
        height: 60px;
        background: linear-gradient(135deg, {COLORS['primary_purple']} 0%, {COLORS['dark_purple']} 100%);
        border-radius: 50%;
        box-shadow: 0 4px 20px rgba(128, 90, 249, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        z-index: 1000;
    }}
    
    .fab:hover {{
        transform: scale(1.1) rotate(90deg);
        box-shadow: 0 6px 25px rgba(128, 90, 249, 0.5);
    }}
    
    /* Animated Cards */
    .task-card {{
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
        border-left: 4px solid {COLORS['primary_purple']};
        position: relative;
        overflow: hidden;
    }}
    
    .task-card::before {{
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, {COLORS['primary_purple']}10, transparent);
        transition: left 0.5s;
    }}
    
    .task-card:hover::before {{
        left: 100%;
    }}
    
    .task-card:hover {{
        transform: translateX(5px);
        box-shadow: 0 6px 25px rgba(0, 0, 0, 0.12);
    }}
    
    /* Status Pills */
    .status-pill {{
        display: inline-block;
        padding: 0.25rem 1rem;
        border-radius: 50px;
        font-size: 0.875rem;
        font-weight: 600;
        margin: 0.25rem;
        animation: fadeIn 0.5s ease;
    }}
    
    .status-active {{
        background: {COLORS['success']}20;
        color: {COLORS['success']};
    }}
    
    .status-pending {{
        background: {COLORS['warning']}20;
        color: {COLORS['warning']};
    }}
    
    .status-completed {{
        background: {COLORS['info']}20;
        color: {COLORS['info']};
    }}
    
    /* Animated Title */
    .animated-title {{
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(90deg, {COLORS['primary_purple']}, {COLORS['coral']}, {COLORS['primary_purple']});
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradient 3s ease infinite;
        text-align: center;
        margin: 2rem 0;
    }}
    
    @keyframes gradient {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* Tooltip */
    .tooltip {{
        position: relative;
        display: inline-block;
    }}
    
    .tooltip .tooltiptext {{
        visibility: hidden;
        width: 200px;
        background-color: {COLORS['navy']};
        color: white;
        text-align: center;
        border-radius: 8px;
        padding: 0.5rem;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.875rem;
    }}
    
    .tooltip:hover .tooltiptext {{
        visibility: visible;
        opacity: 1;
    }}
    
    /* Loading Animation */
    .loader {{
        width: 50px;
        height: 50px;
        border: 3px solid {COLORS['light_purple']};
        border-top-color: {COLORS['primary_purple']};
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 2rem auto;
    }}
    
    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}
    
    /* Notification Badge */
    .notification-badge {{
        position: absolute;
        top: -8px;
        right: -8px;
        background: {COLORS['coral']};
        color: white;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 700;
        animation: pulse 2s infinite;
    }}
    
    @keyframes pulse {{
        0% {{ transform: scale(1); box-shadow: 0 0 0 0 {COLORS['coral']}40; }}
        70% {{ transform: scale(1.1); box-shadow: 0 0 0 10px transparent; }}
        100% {{ transform: scale(1); box-shadow: 0 0 0 0 transparent; }}
    }}
    
    /* Responsive Design */
    @media (max-width: 768px) {{
        .glass-card {{
            padding: 1rem;
            margin: 0.5rem 0;
        }}
        
        .animated-title {{
            font-size: 2rem;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def create_animated_header(title, subtitle=None):
    """Create an animated header with gradient text"""
    header_html = f"""
    <div style="text-align: center; margin: 2rem 0;">
        <h1 class="animated-title">{title}</h1>
        {f'<p style="font-size: 1.25rem; color: {COLORS["dark_gray"]}; margin-top: -1rem;">{subtitle}</p>' if subtitle else ''}
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

def create_glass_card(content, title=None, icon=None):
    """Create a glassmorphism card with content"""
    # Create a container
    with st.container():
        # Add custom CSS class to this specific container
        st.markdown(
            f'<div class="glass-card-wrapper" style="padding: 1.5rem; margin: 1rem 0;">',
            unsafe_allow_html=True
        )
        
        # Add title if provided
        if title:
            if icon:
                st.markdown(f"### {icon} {title}")
            else:
                st.markdown(f"### {title}")
        
        # Execute the content
        if callable(content):
            content()
        else:
            st.write(content)
        
        # Close the wrapper
        st.markdown('</div>', unsafe_allow_html=True)
def show_loading_with_progress(message, current_step=None, total_steps=None):
    """Show loading animation with optional progress"""
    if current_step and total_steps:
        progress = (current_step / total_steps) * 100
        progress_html = f"""
        <div style="text-align: center; padding: 2rem;">
            <div class="loader"></div>
            <p style="color: {COLORS['dark_gray']}; margin-top: 1rem;">{message}</p>
            <div style="margin-top: 1rem;">
                <div style="background: #e0e0e0; border-radius: 10px; overflow: hidden;">
                    <div style="background: {COLORS['primary_purple']}; width: {progress}%; height: 6px;"></div>
                </div>
                <p style="color: {COLORS['dark_gray']}; font-size: 0.875rem; margin-top: 0.5rem;">
                    Step {current_step} of {total_steps}
                </p>
            </div>
        </div>
        """
    else:
        progress_html = f"""
        <div style="text-align: center; padding: 2rem;">
            <div class="loader"></div>
            <p style="color: {COLORS['dark_gray']}; margin-top: 1rem;">{message}</p>
        </div>
        """
    return st.markdown(progress_html, unsafe_allow_html=True)

def create_progress_steps(current_step, total_steps, step_labels):
    """Create a simple, clean progress indicator"""
    progress = (current_step / total_steps) * 100
    
    # Simple progress bar
    progress_html = f"""
    <div style="width: 100%; background-color: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 20px 0;">
        <div style="width: {progress}%; background: linear-gradient(90deg, #805AF9, #FF6666); height: 10px;"></div>
    </div>
    """
    st.markdown(progress_html, unsafe_allow_html=True)
    
    # Step indicators using columns
    cols = st.columns(total_steps)
    for i, (col, label) in enumerate(zip(cols, step_labels)):
        step_num = i + 1
        is_complete = step_num < current_step
        is_current = step_num == current_step
        
        with col:
            if is_complete:
                st.markdown(f"✅ **{label}**")
            elif is_current:
                st.markdown(f"🔵 **{label}**")
            else:
                st.markdown(f"⭕ {label}")

def create_task_card(task_title, task_info, status="pending", assignee=None):
    """Create an interactive task card"""
    status_class = f"status-{status}"
    status_text = status.capitalize()
    
    assignee_html = ""
    if assignee:
        assignee_html = f"""
        <div style="display: flex; align-items: center; margin-top: 1rem;">
            <div style="
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: {COLORS['primary_purple']};
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 0.5rem;
                font-weight: 600;
            ">{assignee[0].upper()}</div>
            <span style="color: {COLORS['dark_gray']};">{assignee}</span>
        </div>
        """
    
    card_html = f"""
    <div class="task-card">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <h4 style="color: {COLORS['navy']}; margin: 0;">{task_title}</h4>
            <span class="status-pill {status_class}">{status_text}</span>
        </div>
        <p style="color: {COLORS['dark_gray']}; margin: 0.5rem 0;">{task_info}</p>
        {assignee_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def create_metric_card(label: str, value: str, delta: float = None, icon: str = None):
    """Create a styled metric card with optional delta and icon."""
    html_lines = []

    # 1) Card container
    html_lines.append(
        '<div class="glass-card" '
        'style="position: relative; text-align: center; padding: 1rem;">'
    )

    # 2) Optional icon
    if icon:
        html_lines.append(
            '<div style="'
            'position: absolute; right: 1rem; top: 1rem; '
            'font-size: 2rem; opacity: 0.2;">'
            f'{icon}'
            '</div>'
        )

    # 3) Value
    html_lines.append(
        '<div style="'
        'font-size: 2.5rem; font-weight: 700; '
        f"color: {COLORS['primary_purple']}; margin: 0.5rem 0;"
        '">'
        f'{value}'
        '</div>'
    )

    # 4) Label
    html_lines.append(
        '<div style="'
        f"color: {COLORS['dark_gray']}; font-size: 1rem;"
        '">'
        f'{label}'
        '</div>'
    )

    # 5) Optional delta
    if delta is not None:
        delta_color = COLORS['success'] if delta > 0 else COLORS['danger']
        delta_icon  = '↑' if delta > 0 else '↓'
        html_lines.append(
            '<div style="'
            f"color: {delta_color}; font-size: 0.875rem; margin-top: 0.5rem;"
            '">'
            f'{delta_icon}{abs(delta)}%'
            '</div>'
        )

    # 6) Close container
    html_lines.append('</div>')

    # Join into one string with line-breaks (for readability in the browser)
    card_html = "\n".join(html_lines)

    # Tell Streamlit to render it as HTML
    st.markdown(card_html, unsafe_allow_html=True)

def create_notification(message, type="info"):
    """Create an animated notification"""
    colors = {
        "success": COLORS['success'],
        "warning": COLORS['warning'],
        "error": COLORS['danger'],
        "info": COLORS['info']
    }
    
    icons = {
        "success": "✓",
        "warning": "⚠",
        "error": "✕",
        "info": "ℹ"
    }
    
    notification_html = f"""
    <div style="
        background: {colors[type]}20;
        border-left: 4px solid {colors[type]};
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        display: flex;
        align-items: center;
        animation: fadeIn 0.5s ease;
    ">
        <div style="
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: {colors[type]};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 1rem;
            font-weight: 700;
        ">{icons[type]}</div>
        <div style="color: {COLORS['dark_gray']};">{message}</div>
    </div>
    """
    st.markdown(notification_html, unsafe_allow_html=True)

def get_prezlab_logo_svg():
    """Generate a PrezLab logo SVG"""
    logo_svg = f"""
    <svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="24" fill="url(#gradient)"/>
        <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{COLORS['primary_purple']};stop-opacity:1" />
                <stop offset="100%" style="stop-color:{COLORS['dark_purple']};stop-opacity:1" />
            </linearGradient>
        </defs>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" 
              font-family="Inter, sans-serif" font-size="48" font-weight="700" fill="white">
            P
        </text>
        <text x="50%" y="75%" text-anchor="middle" 
              font-family="Inter, sans-serif" font-size="12" font-weight="500" fill="white">
            PREZLAB
        </text>
    </svg>
    """
    return logo_svg

def create_floating_action_button(icon="➕"):
    """Create a floating action button"""
    fab_html = f"""
    <div class="fab" onclick="alert('Add new task')">
        <span style="color: white; font-size: 1.5rem;">{icon}</span>
    </div>
    """
    st.markdown(fab_html, unsafe_allow_html=True)

def create_interactive_dashboard():
    """Create an interactive dashboard with metrics"""
    # Inject the enhanced CSS
    inject_enhanced_css()
    
    # Header
    create_animated_header("Task Management Dashboard", "Welcome back! Here's your overview")
    
    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        create_metric_card("Active Tasks", "12", delta=8, icon="📋")
    
    with col2:
        create_metric_card("Completed", "45", delta=15, icon="✅")
    
    with col3:
        create_metric_card("Designers", "8", icon="👥")
    
    with col4:
        create_metric_card("On Time", "92%", delta=5, icon="⏱️")
    
    # Recent Tasks Section
    st.markdown("<br>", unsafe_allow_html=True)
    create_glass_card(
        content="",
        title="Recent Tasks",
        icon="📌"
    )
    
    # Task Cards
    create_task_card(
        "PowerPoint Presentation - Q4 Results",
        "Due: Tomorrow • Client: ABC Corp • 15 slides",
        status="active",
        assignee="John Designer"
    )
    
    create_task_card(
        "Brand Guidelines Document",
        "Due: Next Week • Client: XYZ Ltd • Arabic & English",
        status="pending",
        assignee="Sarah Creative"
    )
    
    # Floating Action Button
    create_floating_action_button()

# Utility function to create a loading animation
def show_loading_animation(message="Loading..."):
    """Show a custom loading animation"""
    loading_html = f"""
    <div style="text-align: center; padding: 2rem;">
        <div class="loader"></div>
        <p style="color: {COLORS['dark_gray']}; margin-top: 1rem;">{message}</p>
    </div>
    """
    return st.markdown(loading_html, unsafe_allow_html=True)

# Function to animate numbers
def animate_number(start, end, duration=1000, prefix="", suffix=""):
    """Create an animated number counter"""
    counter_id = f"counter_{hash(str(end))}"
    script = f"""
    <div id="{counter_id}" style="
        font-size: 2.5rem;
        font-weight: 700;
        color: {COLORS['primary_purple']};
    ">{prefix}{start}{suffix}</div>
    
    <script>
    (function() {{
        let current = {start};
        const target = {end};
        const increment = (target - current) / ({duration} / 16);
        const counter = document.getElementById('{counter_id}');
        
        const timer = setInterval(() => {{
            current += increment;
            if ((increment > 0 && current >= target) || (increment < 0 && current <= target)) {{
                current = target;
                clearInterval(timer);
            }}
            counter.textContent = '{prefix}' + Math.round(current) + '{suffix}';
        }}, 16);
    }})();
    </script>
    """
    st.markdown(script, unsafe_allow_html=True)

# Enhanced form styling
def style_form_container():
    """Apply enhanced styling to form containers"""
    form_css = f"""
    <style>
    /* Enhanced Form Styling */
    [data-testid="stForm"] {{
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(128, 90, 249, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }}
    
    /* Form Labels */
    [data-testid="stForm"] label {{
        color: {COLORS['navy']};
        font-weight: 600;
        margin-bottom: 0.5rem;
    }}
    
    /* Submit Button Special Styling */
    [data-testid="stForm"] [type="submit"] {{
        background: linear-gradient(135deg, {COLORS['primary_purple']} 0%, {COLORS['dark_purple']} 100%);
        width: 100%;
        margin-top: 1rem;
    }}
    </style>
    """
    st.markdown(form_css, unsafe_allow_html=True)
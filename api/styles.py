"""
Custom CSS for ARIS RAG Application
Premium "Glassmorphism" Design with Dark Mode focus.
"""

def get_custom_css():
    return """
    <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

        /* Root Variables for Theming */
        :root {
            --primary-color: #3b82f6; /* Blue 500 */
            --primary-hover: #2563eb; /* Blue 600 */
            --secondary-color: #8b5cf6; /* Violet 500 */
            --background-dark: #0f172a; /* Slate 900 */
            --card-bg: rgba(30, 41, 59, 0.7); /* Slate 800 with opacity */
            --text-primary: #f8fafc; /* Slate 50 */
            --text-secondary: #94a3b8; /* Slate 400 */
            --border-color: rgba(148, 163, 184, 0.1);
            --gradient-1: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            --glass-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --glass-border: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Global Font Settings */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: var(--text-primary);
        }
        
        /* Code Font */
        code, .stCodeBlock, pre {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* App Background */
        .stApp {
            background-color: var(--background-dark);
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.1) 0px, transparent 50%),
                radial-gradient(at 0% 100%, rgba(236, 72, 153, 0.1) 0px, transparent 50%);
            background-attachment: fixed;
        }

        /* Header Styling */
        header[data-testid="stHeader"] {
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: var(--glass-border);
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.95);
            border-right: var(--glass-border);
        }

        section[data-testid="stSidebar"] .stMarkdown h1, 
        section[data-testid="stSidebar"] .stMarkdown h2, 
        section[data-testid="stSidebar"] .stMarkdown h3 {
            color: var(--text-primary);
            font-weight: 600;
        }

        /* Card / Container Styling (Glassmorphism) */
        .stMarkdown div[data-testid="stExpander"], 
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
            /* We can't target all internal divs easily, but we can style specific components */
        }
        
        /* Custom Card Class (Usage: <div class="glass-card">...</div>) */
        .glass-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: var(--glass-border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--glass-shadow);
            margin-bottom: 20px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .glass-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: rgba(59, 130, 246, 0.3);
        }

        /* Buttons */
        .stButton > button {
            background: var(--card-bg);
            color: var(--text-primary);
            border: var(--glass-border);
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: var(--glass-shadow);
        }

        .stButton > button:hover {
            background: rgba(59, 130, 246, 0.1);
            border-color: var(--primary-color);
            color: white;
        }
        
        .stButton > button:active {
            transform: scale(0.98);
        }

        /* Primary Button */
        .stButton > button[kind="primary"] {
            background: var(--gradient-1);
            border: none;
            color: white;
            font-weight: 600;
            box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.4);
        }

        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.23);
            filter: brightness(1.1);
        }

        /* Inputs (Text Input, Selectbox, Number Input) */
        .stTextInput > div > div, 
        .stSelectbox > div > div, 
        .stNumberInput > div > div,
        .stTextArea > div > div {
            background-color: rgba(30, 41, 59, 0.5) !important;
            border: var(--glass-border) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
            backdrop-filter: blur(4px);
        }
        
        .stTextInput > div > div:focus-within, 
        .stSelectbox > div > div:focus-within {
            border-color: var(--primary-color) !important;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
        }

        /* Chat Messages */
        .stChatMessage {
            background: transparent;
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }

        .stChatMessage[data-testid="stChatMessage"]:nth-child(2n) {
             /* User Message */
             background: rgba(59, 130, 246, 0.1);
             border: 1px solid rgba(59, 130, 246, 0.2);
        }
        
        .stChatMessage[data-testid="stChatMessage"]:nth-child(2n+1) {
             /* Assistant Message */
             background: var(--card-bg);
             border: var(--glass-border);
        }
        
        /* Expanders */
        .streamlit-expanderHeader {
            background-color: rgba(30, 41, 59, 0.4) !important;
            border-radius: 8px !important;
            border: var(--glass-border) !important;
            color: var(--text-primary) !important;
        }
        
        .streamlit-expanderContent {
            background-color: transparent !important;
            border: none !important;
        }

        /* Metrics */
        div[data-testid="stMetric"] {
            background: var(--card-bg);
            padding: 15px;
            border-radius: 10px;
            border: var(--glass-border);
            text-align: center;
        }
        
        div[data-testid="stMetricLabel"] {
            color: var(--text-secondary);
            font-size: 0.85rem !important;
        }
        
        div[data-testid="stMetricValue"] {
            color: var(--text-primary);
            font-weight: 700;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 1.5rem !important;
        }

        /* Progress Bar */
        .stProgress > div > div > div > div {
            background: var(--gradient-1);
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(15, 23, 42, 0.5); 
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(148, 163, 184, 0.3); 
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(148, 163, 184, 0.5); 
        }

        /* Utility Classes for Custom HTML */
        .hero-header {
            text-align: center;
            padding: 3rem 1rem;
            margin-bottom: 2rem;
            background: radial-gradient(circle at center, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
        }
        
        .hero-title {
            font-size: 3.5rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.05em;
        }
        
        .hero-subtitle {
            font-size: 1.25rem;
            color: var(--text-secondary);
            max-width: 600px;
            margin: 0 auto;
        }

        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .badge-success {
            background-color: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .badge-warning {
            background-color: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        
        .badge-error {
            background-color: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .badge-info {
            background-color: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

    </style>
    """

def get_glass_card(title, content, color="slate"):
    """
    Helper to generate HTML for a glassmorphism card.
    """
    return f"""
    <div class="glass-card">
        <h3 style="margin-top: 0; font-size: 1.1rem; font-weight: 600; color: white;">{title}</h3>
        <div style="color: #cbd5e1; font-size: 0.95rem;">
            {content}
        </div>
    </div>
    """

# app.py — Streamlit UI for the Personal Chef AI agent
# Single-page chatbot interface inspired by Microsoft's Streamlit UI Template App 3.
# Custom CSS is injected directly — no external stylesheet required.

import os
import streamlit as st
from dotenv import load_dotenv
from agent import create_chef_agent, stream_agent_response

# Load .env for local development (no-op in production / Streamlit Cloud)
load_dotenv()

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Chef AI",
    page_icon="🍳",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* Hide default Streamlit chrome */
        #MainMenu  { visibility: hidden; }
        footer     { visibility: hidden; }
        header     { visibility: hidden; }

        /* ── App header ── */
        .chef-header {
            text-align: center;
            padding: 2rem 0 0.5rem;
        }
        .chef-header h1 {
            font-size: 2.4rem;
            font-weight: 800;
            color: #FF6B35;
            margin-bottom: 0.2rem;
        }
        .chef-header p {
            font-size: 1rem;
            color: #AAAAAA;
            margin-top: 0;
        }

        /* ── Divider ── */
        .chef-divider {
            border: none;
            border-top: 1px solid #2E2E4A;
            margin: 0.5rem 0 1.5rem;
        }

        /* ── Chat message bubbles ── */
        .stChatMessage {
            border-radius: 12px;
            margin-bottom: 0.5rem;
        }

        /* ── Chat input box ── */
        .stChatInputContainer textarea {
            border-radius: 10px !important;
            border: 1px solid #FF6B35 !important;
            background-color: #16213E !important;
            color: #EAEAEA !important;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {
            background-color: #16213E;
        }

        /* ── Tool / thinking indicator ── */
        .tool-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #FF6B35;
            font-style: italic;
            padding: 6px 0;
            font-size: 0.9rem;
        }
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 107, 53, 0.3);
            border-top-color: #FF6B35;
            border-radius: 50%;
            animation: spin 0.75s linear infinite;
            flex-shrink: 0;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar — API Key ─────────────────────────────────────────────────────────
# Prefer key from .env / environment; fall back to manual input in the sidebar.
env_key = os.getenv("OPENAI_API_KEY", "")

with st.sidebar:
    st.markdown("### 🔑 API Key")
    if env_key:
        st.success("API key loaded from environment.")
        openai_key = env_key
    else:
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Your key is used only in this session and never stored.",
        )
        st.markdown("[Get a free key](https://platform.openai.com/api-keys)")
        st.markdown("---")
        st.markdown(
            "<small>Your key lives only in memory for this session and is never "
            "stored or logged.</small>",
            unsafe_allow_html=True,
        )

    if not openai_key:
        st.info("Enter your OpenAI API key to start cooking.")
        st.stop()

# ── Session state — initialise agent and chat history ────────────────────────
if "agent" not in st.session_state or st.session_state.get("agent_key") != openai_key:
    # (Re-)create the agent whenever the key changes
    st.session_state.agent = create_chef_agent(openai_key)
    st.session_state.agent_key = openai_key
    st.session_state.thread_id = "chef_session"
    st.session_state.messages = []  # list of {"role": ..., "content": ...}

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="chef-header">
        <h1>🍳 Personal Chef AI</h1>
        <p>Your AI-powered kitchen companion — recipes, substitutions, and meal plans.</p>
    </div>
    <hr class="chef-divider">
    """,
    unsafe_allow_html=True,
)

# ── Display chat history ──────────────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── Starter hint when chat is empty ──────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        """
        <div style="text-align:center; color:#666; margin-top:3rem;">
            <p>👋 ¡Hola! Soy tu chef personal. Prueba preguntándome:</p>
            <p><em>"¿Cómo hago una paella valenciana?"</em></p>
            <p><em>"¿Qué puedo usar como sustituto del pimentón?"</em></p>
            <p><em>"Planifica una semana de comidas saludables para dos personas."</em></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Tool label helper ─────────────────────────────────────────────────────────
def _tool_label(tool_name: str, args: dict) -> str:
    """Return a human-readable HTML label for a tool call."""
    if tool_name == "web_search":
        query = args.get("query", "")
        return f'🔍 Buscando: <em>"{query}"</em>'
    if tool_name == "fetch_page":
        url = args.get("url", "")
        return f'📖 Leyendo página: <em>{url}</em>'
    if tool_name == "get_ingredient_substitutes":
        ingredient = args.get("ingredient", "")
        suffix = f" para <em>{ingredient}</em>" if ingredient else ""
        return f"🔄 Buscando sustitutos{suffix}…"
    if tool_name == "create_meal_plan":
        return "📅 Creando plan de comidas…"
    return f"🔧 Ejecutando <em>{tool_name}</em>…"


# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask your chef anything…")

if user_input:
    # Show the user's message immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Stream the agent's response
    with st.chat_message("assistant"):
        tool_slot = st.empty()   # spinner / tool status
        text_slot = st.empty()   # streaming text
        response_text = ""

        # Show initial "thinking" indicator immediately
        tool_slot.markdown(
            '<div class="tool-indicator">'
            '<div class="spinner"></div><span>Pensando…</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        try:
            for event in stream_agent_response(
                st.session_state.agent,
                user_input,
                st.session_state.thread_id,
            ):
                kind = event[0]

                if kind == "tool_start":
                    _, tool_name, tool_args = event
                    label = _tool_label(tool_name, tool_args)
                    tool_slot.markdown(
                        f'<div class="tool-indicator">'
                        f'<div class="spinner"></div><span>{label}</span>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                elif kind == "tool_end":
                    # Keep spinner visible until text starts flowing
                    pass

                elif kind == "text":
                    tool_slot.empty()  # hide spinner once text arrives
                    response_text += event[1]
                    text_slot.markdown(response_text + "▌")

            # Finalise — remove typing cursor
            text_slot.markdown(response_text)
            tool_slot.empty()

        except Exception as e:
            tool_slot.empty()
            error_msg = (
                "⚠️ Something went wrong. Please check your API key and try again.\n\n"
                f"*Error: {e}*"
            )
            text_slot.markdown(error_msg)
            response_text = error_msg

    # Save the assistant reply to history
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )

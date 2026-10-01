# app.py — Streamlit UI for the Personal Chef AI agent
# Single-page chatbot interface inspired by Microsoft's Streamlit UI Template App 3.
# Custom CSS is injected directly — no external stylesheet required.

import io
import os
from html import escape
from uuid import uuid4

import openai
import streamlit as st
from dotenv import load_dotenv

from agent import create_chef_agent, stream_agent_response
from providers import (
    DEFAULT_OPENAI_MODEL, DEFAULT_ROUTER_MODEL, DEMO_SESSION_TURNS,
    MAX_INPUT_CHARS, DemoBudget, ModelSettings, public_error,
    EmptyResponseError, record_failure,
)

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
        /* Keep header controls available so narrow screens can close the sidebar. */

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

def server_setting(name, default=""):
    value = os.getenv(name)
    if value is not None:
        return value.strip()
    try:
        return str(st.secrets.get(name, default)).strip()
    except FileNotFoundError:
        return default


@st.cache_resource
def demo_budget():
    return DemoBudget()


settings = None
voice_key = ""
st.session_state.setdefault("demo_turns", 0)

with st.sidebar:
    st.markdown("### 🍳 Empieza a cocinar")
    mode = st.radio("Acceso", ["Probar gratis", "Mi clave de OpenRouter", "Mi clave de OpenAI"])
    if mode == "Probar gratis":
        key = server_setting("OPENROUTER_API_KEY")
        model_id = server_setting("OPENROUTER_DEMO_MODEL", DEFAULT_ROUTER_MODEL)
        st.caption("Prueba por texto sin cuenta ni clave. Disponibilidad limitada.")
        quota_label = st.empty()
        quota_label.caption(f"{max(0, DEMO_SESSION_TURNS - st.session_state.demo_turns)} consultas disponibles en esta sesión.")
        if key:
            try:
                settings = ModelSettings("openrouter", key, model_id, demo=True)
            except ValueError:
                st.warning("La configuración de la demo necesita revisión.")
        else:
            st.info("La demo aún no está activada. Puedes probar con tu propia clave.")
    else:
        provider = "openrouter" if mode == "Mi clave de OpenRouter" else "openai"
        key = st.text_input("API key", type="password", key=f"key_{provider}").strip()
        default_model = DEFAULT_ROUTER_MODEL if provider == "openrouter" else DEFAULT_OPENAI_MODEL
        model_id = st.text_input("Modelo", value=default_model, key=f"model_{provider}").strip()
        st.caption("Tu clave se mantiene en la memoria de esta sesión. Las llamadas se realizan desde el servidor y usan tu cuenta del proveedor.")
        if provider == "openrouter":
            st.markdown("[Crear clave de OpenRouter](https://openrouter.ai/settings/keys)")
        if key and model_id:
            settings = ModelSettings(provider, key, model_id)
        if provider == "openai":
            voice_key = key

    st.caption("Las consultas se envían al proveedor elegido; las búsquedas, a DuckDuckGo.")
    if st.button("Nueva conversación"):
        st.session_state.pop("agent_settings", None)

# A different provider/model/key starts a fresh conversation. Demo quota survives.
if st.session_state.get("agent_settings") != settings or "messages" not in st.session_state:
    st.session_state.pop("agent", None)
    st.session_state.agent_settings = settings
    st.session_state.thread_id = str(uuid4())
    st.session_state.messages = []
    st.session_state.pop("_last_audio", None)

if settings and "agent" not in st.session_state:
    try:
        st.session_state.agent = create_chef_agent(settings)
    except Exception as exc:
        st.error(public_error(exc))

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="chef-header">
        <h1>🍳 Personal Chef AI</h1>
        <p>Tu compañero de cocina: recetas, sustituciones y menús semanales.</p>
    </div>
    <hr class="chef-divider">
    """,
    unsafe_allow_html=True,
)

# ── Display chat history ──────────────────────────────────────────────────────
def format_plan(items):
    icons = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}
    return "\n\n".join(
        f"{icons.get(item.get('status'), '⬜')} {item.get('content', '')}"
        for item in items
    )


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("plan"):
            with st.expander("Plan de trabajo", expanded=False):
                st.markdown(format_plan(message["plan"]))
        st.markdown(message["content"])

# ── Starter hint when chat is empty ──────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        """
        <div style="text-align:center; color:#666; margin-top:3rem;">
            <p>👋 ¡Hola! Soy tu chef personal. Prueba preguntándome:</p>
            <p><em>"¿Cómo hago una paella valenciana?"</em></p>
            <p><em>"¿Qué puedo usar como sustituto del pimentón?"</em></p>
            <p><em>"Planifica cinco cenas vegetarianas para dos personas y reutiliza ingredientes."</em></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Tool label helper ─────────────────────────────────────────────────────────
def _tool_label(tool_name: str, args: dict) -> str:
    """Return a human-readable HTML label for a tool call."""
    args = {k: escape(str(v)) for k, v in args.items()}
    tool_name = escape(tool_name)
    if tool_name == "write_todos":
        return "📋 Organizando el menú…"
    if tool_name == "consolidate_shopping_list":
        return "🛒 Sumando la lista de compra…"
    if tool_name in {"write_file", "read_file", "edit_file", "ls", "glob", "grep"}:
        return "📝 Consultando las notas de esta conversación…"
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


# ── Audio transcription helper ────────────────────────────────────────────────
def _transcribe(audio_bytes: bytes, api_key: str) -> str:
    client = openai.OpenAI(api_key=api_key)
    buf = io.BytesIO(audio_bytes)
    buf.name = "audio.wav"
    return client.audio.transcriptions.create(model="whisper-1", file=buf).text


# ── Inputs: text + audio ──────────────────────────────────────────────────────
ready = settings is not None and "agent" in st.session_state
exhausted = bool(settings and settings.demo and st.session_state.demo_turns >= DEMO_SESSION_TURNS)
user_input = st.chat_input("¿Qué te apetece cocinar?", disabled=not ready or exhausted, max_chars=MAX_INPUT_CHARS)
if exhausted:
    st.info("Has terminado las consultas de prueba de esta sesión. Puedes continuar con tu propia clave.")

# Audio recorder — appears below the chat bar
audio_value = st.audio_input("🎤 Graba tu pregunta", key="audio_recorder", disabled=not ready or not voice_key)
if not voice_key:
    st.caption("La entrada por voz está disponible con tu propia clave de OpenAI.")

if ready and voice_key and audio_value and audio_value != st.session_state.get("_last_audio"):
    st.session_state["_last_audio"] = audio_value
    with st.spinner("Transcribing…"):
        try:
            user_input = _transcribe(audio_value.read(), voice_key)
        except Exception as exc:
            st.error(public_error(exc))

if user_input and ready and not exhausted:
    if len(user_input) > MAX_INPUT_CHARS:
        st.warning(f"Usa una pregunta de hasta {MAX_INPUT_CHARS} caracteres.")
        st.stop()
    if settings.demo:
        st.session_state.demo_turns += 1
        quota_label.caption(f"{max(0, DEMO_SESSION_TURNS - st.session_state.demo_turns)} consultas disponibles en esta sesión.")
    # Show the user's message immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Stream the agent's response
    with st.chat_message("assistant"):
        tool_slot = st.empty()   # spinner / tool status
        plan_slot = st.empty()
        text_slot = st.empty()   # streaming text
        response_text = ""
        plan_items = []
        stage = "model"

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
                callbacks=[demo_budget()] if settings.demo else [],
            ):
                kind = event[0]

                if kind == "plan":
                    plan_items = event[1]
                    plan_slot.markdown("**Plan de trabajo**\n\n" + format_plan(plan_items))
                elif kind == "tool_start":
                    _, tool_name, tool_args = event
                    stage = tool_name
                    label = _tool_label(tool_name, tool_args)
                    tool_slot.markdown(
                        f'<div class="tool-indicator">'
                        f'<div class="spinner"></div><span>{label}</span>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                elif kind == "tool_end":
                    # Keep spinner visible until text starts flowing
                    stage = "model_after_tool"

                elif kind == "text":
                    stage = "response"
                    tool_slot.empty()  # hide spinner once text arrives
                    response_text += event[1]
                    text_slot.markdown(response_text + "▌")

            # Finalise — remove typing cursor
            if not response_text.strip():
                raise EmptyResponseError()
            text_slot.markdown(response_text)
            tool_slot.empty()

        except Exception as e:
            tool_slot.empty()
            reference = record_failure(e, settings.provider, settings.model, stage)
            error_msg = "⚠️ " + public_error(e)
            error_msg += f"\n\nReferencia: `{reference}`."
            error_msg += "\n\nLa próxima consulta empezará con un contexto nuevo."
            # Drop potentially incomplete tool-call history after an interrupted run.
            st.session_state.pop("agent", None)
            if response_text.strip():
                response_text = "**Respuesta incompleta; no se ha terminado de verificar.**\n\n" + response_text + "\n\n---\n\n" + error_msg
            else:
                response_text = error_msg
            text_slot.markdown(response_text)

    # Save the assistant reply to history
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text, "plan": plan_items}
    )

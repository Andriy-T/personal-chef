# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app locally
streamlit run app.py

# Set up API key for local dev
cp .env.example .env   # then edit .env with your OpenAI key
```

## Architecture

This is a single-page Streamlit chatbot backed by a LangGraph ReAct agent.

**Entry point:** `app.py` — Streamlit UI. Manages session state (agent instance, thread ID, message history). The agent is re-created whenever the API key changes. Responses are streamed token-by-token via `st.write_stream`.

**Agent layer:** `agent.py` — Creates the LangGraph agent via `create_react_agent` with `InMemorySaver` for per-session conversation memory. The `stream_agent_response` generator filters out tool call/result chunks, yielding only final AI text tokens (identified by `langgraph_node == "agent"`).

**Tools:** `tools.py` — Four tools registered with the agent:
- `web_search` — `DuckDuckGoSearchRun`, no API key needed; used for recipe lookups
- `get_recipe` — prompt scaffold that instructs the LLM to format a recipe response
- `get_ingredient_substitutes` — prompt scaffold for substitution suggestions
- `create_meal_plan` — prompt scaffold for weekly meal planning

Note: `get_recipe`, `get_ingredient_substitutes`, and `create_meal_plan` are prompt scaffolds (they return instruction strings to guide the LLM), not tools that call external APIs.

**Key design decision:** The system prompt (`SYSTEM_PROMPT` in `agent.py`) instructs the agent to always call `web_search` before answering recipe requests and to cite the source URL. The chef persona responds in Spanish by default but mirrors the user's language.

**API key flow:** No key is stored server-side. `OPENAI_API_KEY` is read from `.env` locally; in production (Streamlit Cloud), the user provides it via the sidebar at runtime.

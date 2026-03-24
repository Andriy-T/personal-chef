# 🍳 Personal Chef AI

An AI-powered personal chef built with **LangChain** and **Streamlit**.
Ask it for recipes, ingredient substitutions, or a full weekly meal plan — by typing or speaking.

> Portfolio project demonstrating the three core pillars of modern AI agent development:
> **tool use**, **conversation memory**, and **multimodality**.

---

## Agent Pillars

### 1. Tool Use
The agent runs a ReAct loop and calls tools autonomously to ground its answers in real data:

| Tool | Purpose |
|------|---------|
| `web_search` | DuckDuckGo search for recipes and food facts |
| `fetch_page` | Reads the full content of a recipe page |
| `get_ingredient_substitutes` | Suggests swaps for missing or restricted ingredients |
| `create_meal_plan` | Builds a personalised weekly menu |

The LLM decides *when* and *how* to call each tool — it never invents a recipe from memory.

### 2. Conversation Memory
Powered by LangGraph's `InMemorySaver` checkpointer. The agent retains full conversation history within a session, so you can ask follow-up questions like *"make it vegetarian"* or *"how long does it keep in the fridge?"* without repeating context.

### 3. Multimodality
Two input modes are supported side by side:

- **Text** — standard chat input
- **Voice** — record a question with the built-in mic widget; the audio is transcribed by OpenAI Whisper (`whisper-1`) and fed into the same agent pipeline

---

## Features

- **Recipe lookup** — step-by-step instructions sourced from real recipe sites
- **Ingredient substitutes** — swap ingredients based on what you have or dietary needs
- **Meal planning** — personalised weekly menus with a shopping list
- **Voice input** — speak your question, get a chef's answer
- **Bring your own key** — no API key is stored; you provide it at runtime

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangChain + LangGraph (`create_react_agent`) |
| LLM | OpenAI GPT-5.4-nano |
| Speech-to-text | OpenAI Whisper (`whisper-1`) |
| UI | Streamlit |
| Config | python-dotenv |
| Deployment | Streamlit Community Cloud |

## Project Structure

```
personal-chef/
├── app.py              # Streamlit UI
├── agent.py            # LangChain agent logic
├── tools.py            # Custom agent tools
├── .streamlit/
│   └── config.toml     # Dark food-inspired theme
├── .env.example        # API key template
├── requirements.txt
└── README.md
```

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Andriy-T/personal-chef.git
cd personal-chef

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API key (for local dev only)
cp .env.example .env
# Edit .env and add your OpenAI key

# 5. Run the app
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser (Chrome recommended).
Enter your OpenAI API key in the sidebar and start chatting.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set `app.py` as the main file
4. No secrets needed — users provide their own API key at runtime

## License

MIT

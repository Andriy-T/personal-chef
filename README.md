# 🍳 Personal Chef AI

An AI-powered personal chef built with **LangChain** and **Streamlit**.
Ask it for recipes, ingredient substitutions, or a full weekly meal plan.

> Portfolio project demonstrating LangChain AI Agent capabilities with tool-use and conversation memory.

<!-- Replace with your own demo GIF once deployed -->
<!-- ![Demo](demo.gif) -->

**[Live Demo →](https://your-app.streamlit.app)** *(update after deployment)*

---

## Features

- **Recipe lookup** — step-by-step instructions for any dish
- **Ingredient substitutes** — swap ingredients based on what you have or dietary needs
- **Meal planning** — personalised weekly menus with a shopping list
- **Conversation memory** — the chef remembers context across the chat session
- **Bring your own key** — no API key is stored; you provide it at runtime

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangChain + LangGraph (`create_react_agent`) |
| LLM | OpenAI GPT-4o-mini |
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

Then open [http://localhost:8501](http://localhost:8501) in your browser.
Enter your OpenAI API key in the sidebar and start chatting.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set `app.py` as the main file
4. No secrets needed — users provide their own API key at runtime

## License

MIT

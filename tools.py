# tools.py — Custom tools for the Personal Chef AI agent
# Each tool is clearly named to showcase LangChain agent tool-use.

import re
import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

# Allowed recipe domains
_ALLOWED_DOMAINS = [
    "recetasderechupete.com",
    "directoalpaladar.es",
    "pequerecetas.es",
]
_SITE_FILTER = " OR ".join(f"site:{d}" for d in _ALLOWED_DOMAINS)

_duckduckgo = DuckDuckGoSearchRun()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_MAX_CHARS = 6000  # keep context manageable


@tool
def web_search(query: str) -> str:
    """Search the web for recipes, cooking techniques, or food information.
    Always use this tool first when the user asks for a recipe.
    The results include URLs — pick the best URL and call fetch_page with it.

    Args:
        query: The search query.
    """
    return _duckduckgo.run(f"{query} ({_SITE_FILTER})")


@tool
def fetch_page(url: str) -> str:
    """Fetch the full text content of a recipe page from a URL.
    Use this after web_search to retrieve the actual recipe instead of guessing.
    Only fetch URLs from trusted recipe sites returned by web_search.

    Args:
        url: The full URL of the recipe page to fetch.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        return f"Error fetching page: {exc}"

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav, ads, scripts, styles
    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:_MAX_CHARS]


@tool
def get_ingredient_substitutes(ingredient: str, reason: str = "") -> str:
    """
    Find practical substitutes for a specific ingredient.
    Use this when the user can't find an ingredient, has dietary restrictions,
    or wants to adapt a recipe.

    Args:
        ingredient: The ingredient that needs to be replaced.
        reason: Optional reason for the substitution (e.g. 'vegan', 'out of stock').
    """
    context = f" Reason for substitution: {reason}." if reason else ""
    return (
        f"Suggest practical substitutes for '{ingredient}'.{context}\n"
        "For each substitute provide:\n"
        "- The replacement ingredient and the exact ratio to use\n"
        "- How it changes the flavor or texture of the dish\n"
        "- Which recipe types it works best in\n"
        "Give 3-5 options and highlight the best one."
    )


@tool
def create_meal_plan(preferences: str, num_days: int = 7) -> str:
    """
    Create a personalised meal plan based on the user's dietary preferences.
    Use this when the user asks for weekly menu ideas or meal planning help.

    Args:
        preferences: Dietary preferences or restrictions (e.g. 'vegetarian', 'low carb').
        num_days: Number of days to plan for (default: 7).
    """
    return (
        f"Create a {num_days}-day meal plan for someone with these preferences: {preferences}.\n"
        "For each day include breakfast, lunch, and dinner.\n"
        "Keep meals varied and realistic to prepare at home.\n"
        "Finish with a consolidated grocery shopping list for all meals."
    )

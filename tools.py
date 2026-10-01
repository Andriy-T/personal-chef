# tools.py — Custom tools for the Personal Chef AI agent
# Each tool is clearly named to showcase LangChain agent tool-use.

import re
import json
import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

_duckduckgo = DuckDuckGoSearchResults(output_format="list", num_results=5)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_MAX_CHARS = 6000  # keep context manageable
_MAX_RETRIES = 3


def extract_recipe_text(html: str) -> str:
    """Prefer publisher recipe metadata; fallback to the main article text."""
    soup = BeautifulSoup(html, "html.parser")

    def instructions(value):
        if isinstance(value, str):
            yield BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        elif isinstance(value, list):
            for item in value:
                yield from instructions(item)
        elif isinstance(value, dict):
            if value.get("text"):
                yield from instructions(value["text"])
            elif value.get("name"):
                yield from instructions(value["name"])
            if value.get("itemListElement"):
                yield from instructions(value["itemListElement"])

    def recipes(value):
        if isinstance(value, list):
            for item in value:
                yield from recipes(item)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if not isinstance(types, list):
                types = []
            if "Recipe" in types:
                yield value
            if "@graph" in value:
                yield from recipes(value["@graph"])

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for recipe in recipes(data):
            if recipe.get("recipeIngredient") and recipe.get("recipeInstructions"):
                fields = {key: recipe[key] for key in (
                    "name", "recipeYield", "prepTime", "cookTime", "totalTime",
                    "recipeIngredient", "recipeInstructions",
                ) if key in recipe}
                fields["recipeInstructions"] = list(instructions(recipe["recipeInstructions"]))
                return json.dumps(fields, ensure_ascii=False)[:_MAX_CHARS]
    for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form"]):
        tag.decompose()
    content = soup.find("article") or soup.find("main") or soup
    return re.sub(r"\n{3,}", "\n\n", content.get_text(separator="\n")).strip()[:_MAX_CHARS]


@tool
def web_search(query: str) -> str:
    """Search the web for recipes, cooking techniques, or food information.
    Always use this tool first when the user asks for a recipe.
    The results include URLs — pick the best URL and call fetch_page with it.

    Args:
        query: The search query.
    """
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            results = _duckduckgo.run(query)
            if not results:
                return "No results found."
            return "\n".join(
                f"- {r['title'][:180]}\n  URL: {r['link']}\n  {r['snippet'][:400]}"
                for r in results
            )
        except Exception as exc:
            last_exc = exc
    return f"Search failed after {_MAX_RETRIES} attempts: {last_exc}"


@tool
def fetch_page(url: str) -> str:
    """Fetch the full text content of a recipe page from a URL.
    Use this after web_search to retrieve the actual recipe instead of guessing.
    Only fetch URLs from trusted recipe sites returned by web_search.

    Args:
        url: The full URL of the recipe page to fetch.
    """
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            break
        except Exception as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES:
                return f"Error fetching page after {_MAX_RETRIES} attempts: {last_exc}"

    return extract_recipe_text(resp.text)


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

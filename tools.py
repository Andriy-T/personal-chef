# tools.py — Custom tools for the Personal Chef AI agent
# Each tool is clearly named to showcase LangChain agent tool-use.

from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

# Web search tool — no API key required
web_search = DuckDuckGoSearchRun(
    name="web_search",
    description=(
        "Search the web for recipes, cooking techniques, or food information. "
        "Always use this tool when the user asks for a recipe. "
        "The results include URLs — extract the source URL and cite it in your response."
    ),
)


@tool
def get_recipe(dish_name: str) -> str:
    """
    Retrieve a full recipe for a specific dish.
    Use this whenever the user asks how to cook something or requests a recipe.

    Args:
        dish_name: The name of the dish to get the recipe for.
    """
    return (
        f"Provide a complete recipe for '{dish_name}'. Include:\n"
        "- A short, appetizing description of the dish\n"
        "- Full ingredients list with exact quantities\n"
        "- Clear step-by-step preparation instructions\n"
        "- Estimated prep and cook time\n"
        "- Serving size and any useful tips\n"
        "Format the response in clean, easy-to-read markdown."
    )


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

"""Deterministic shopping totals; quantities are supplied by the agent, not verified here."""

from decimal import Decimal
from fractions import Fraction
from typing import Annotated

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator


class ShoppingIngredient(BaseModel):
    ingredient: str = Field(min_length=1, max_length=100)
    quantity: Decimal | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False,
                                    description="Decimal amount, or null for unspecified/al gusto quantities. Never guess a number.")
    unit: str = Field(min_length=1, max_length=30)
    estimated: bool = Field(description="True when quantity is estimated rather than taken from a recipe source.")

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_quantity(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"al gusto", "cantidad necesaria"}:
                return None
            value = {"¼": "1/4", "½": "1/2", "¾": "3/4", "⅓": "1/3", "⅔": "2/3"}.get(value, value)
            if "/" in value:
                try:
                    fraction = Fraction(value)
                    return Decimal(fraction.numerator) / Decimal(fraction.denominator)
                except (ValueError, ZeroDivisionError):
                    raise ValueError("Use a decimal, a fraction, or null for an unspecified quantity.") from None
        return value


class MealRecipe(BaseModel):
    meal: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, description="Exact URL of the recipe that was read.")
    source_servings: Decimal = Field(gt=0, le=100, allow_inf_nan=False,
                                     description="Yield of the source recipe, not the total weekly portions.")
    servings_estimated: bool = Field(description="True if the source yield was not specified and had to be estimated.")
    ingredients: list[ShoppingIngredient] = Field(min_length=1, max_length=40,
        description="Original source amounts BEFORE scaling. Mark substitutions or invented amounts as estimated.")


@tool
def scale_meal_plan(
    people_per_meal: Annotated[int, Field(ge=1, le=20)],
    meals: Annotated[list[MealRecipe], Field(min_length=1, max_length=14)],
) -> str:
    """Scale each dinner's original recipe to people_per_meal, then sum the shopping.

    For five dinners for two: people_per_meal=2, with five meals (NOT 10 people).
    Copy unscaled ingredient amounts and source yield from each fetched recipe.
    Never multiply ingredient amounts yourself. Unknown amounts remain null.
    Checks arithmetic, not source fidelity or dietary restrictions.
    """
    ingredients = []
    lines = [f"{len(meals)} comidas × {people_per_meal} personas = {len(meals) * people_per_meal} raciones totales."]
    for meal in meals:
        factor = Decimal(people_per_meal) / meal.source_servings
        lines.append(f"- {meal.meal}: receta de {meal.source_servings} a {people_per_meal} raciones; fuente: {meal.source_url}"
                     + (" (raciones originales estimadas)" if meal.servings_estimated else ""))
        for ingredient in meal.ingredients:
            ingredients.append(ingredient.model_copy(update={
                "quantity": None if ingredient.quantity is None else ingredient.quantity * factor,
                "estimated": ingredient.estimated or meal.servings_estimated,
            }))
    return "\n".join(lines) + "\n\n" + consolidate_shopping_list.func(ingredients)


@tool
def consolidate_shopping_list(
    ingredients: Annotated[list[ShoppingIngredient], Field(min_length=1, max_length=100)],
) -> str:
    """Sum the shopping ingredients for all requested portions and days.

    Pass one item per ingredient per meal, already scaled to the requested servings.
    Keep distinct preparations/names separate. Mark estimated quantities honestly.
    Converts kg to g and l to ml. Never converts volume to weight or guesses units.
    This checks arithmetic only; it does not verify recipe sources or dietary safety.
    """
    aliases = {"kg": ("g", 1000), "kilogramos": ("g", 1000),
               "gramos": ("g", 1), "g": ("g", 1),
               "l": ("ml", 1000), "litros": ("ml", 1000), "ml": ("ml", 1),
               "unidad": ("unidad", 1), "unidades": ("unidad", 1)}
    totals = {}
    for item in ingredients:
        name = " ".join(item.ingredient.lower().split())
        raw_unit = " ".join(item.unit.lower().split())
        if not name or not raw_unit:
            raise ValueError("Ingredient and unit cannot be blank.")
        unit, factor = aliases.get(raw_unit, (raw_unit, 1))
        key = (name, unit)
        total, estimated, unspecified = totals.get(key, (Decimal(0), False, False))
        if item.quantity is None:
            unspecified = True
        else:
            total += item.quantity * factor
        totals[key] = (total, estimated or item.estimated, unspecified)
    lines = ["Lista consolidada (cantidades para todas las raciones indicadas):"]
    for (name, unit), (total, estimated, unspecified) in sorted(totals.items()):
        quantity = format(total.normalize(), "f")
        suffix = " (estimación)" if estimated else ""
        if not total:
            lines.append(f"- {name}: cantidad sin especificar (al gusto){suffix}")
        else:
            unknown_note = "; además, cantidad sin especificar" if unspecified else ""
            lines.append(f"- {name}: {quantity} {unit}{suffix}{unknown_note}")
    return "\n".join(lines)

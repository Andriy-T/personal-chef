import unittest
from pydantic import ValidationError
from planning import consolidate_shopping_list, scale_meal_plan


class PlanningTests(unittest.TestCase):
    def test_five_dinners_scale_to_two_each_not_ten_each(self):
        meals = [{"meal": f"Cena {day}", "source_url": "https://example.com/recipe",
                  "source_servings": 4, "servings_estimated": day == 0,
                  "ingredients": [
                      {"ingredient": "arroz", "quantity": 400, "unit": "g", "estimated": False},
                      {"ingredient": "sal", "quantity": None, "unit": "g", "estimated": False},
                  ]} for day in range(5)]
        result = scale_meal_plan.invoke({"people_per_meal": 2, "meals": meals})
        self.assertIn("10 raciones totales", result)
        self.assertIn("arroz: 1000 g (estimación)", result)
        self.assertIn("sal: cantidad sin especificar", result)
        self.assertEqual(result.count("receta de 4 a 2 raciones"), 5)

    def test_totals_convert_compatible_units_keep_estimates_and_distinct_forms(self):
        result = consolidate_shopping_list.invoke({"ingredients": [
            {"ingredient": "Tomate", "quantity": "0.5", "unit": "kg", "estimated": False},
            {"ingredient": " tomate ", "quantity": "250", "unit": "g", "estimated": True},
            {"ingredient": "Tomate", "quantity": "2", "unit": "unidades", "estimated": False},
            {"ingredient": "tomate triturado", "quantity": "200", "unit": "g", "estimated": False},
        ]})
        self.assertIn("tomate: 750 g (estimación)", result)
        self.assertIn("tomate: 2 unidad", result)
        self.assertIn("tomate triturado: 200 g", result)

    def test_invalid_quantities_are_rejected(self):
        for amount in [-1, 0, "NaN", "Infinity"]:
            with self.assertRaises(ValidationError):
                consolidate_shopping_list.invoke({"ingredients": [{
                    "ingredient": "pan", "quantity": amount, "unit": "g", "estimated": False,
                }]})

    def test_unspecified_amount_is_not_invented_and_fractions_are_supported(self):
        result = consolidate_shopping_list.invoke({"ingredients": [
            {"ingredient": "sal", "quantity": "al gusto", "unit": "g", "estimated": False},
            {"ingredient": "aceite", "quantity": None, "unit": "ml", "estimated": False},
            {"ingredient": "aceite", "quantity": 10, "unit": "ml", "estimated": False},
            {"ingredient": "pimentón", "quantity": "¼", "unit": "cucharadita", "estimated": False},
            {"ingredient": "pimentón", "quantity": "1/2", "unit": "cucharadita", "estimated": False},
        ]})
        self.assertIn("sal: cantidad sin especificar", result)
        self.assertIn("aceite: 10 ml; además, cantidad sin especificar", result)
        self.assertIn("pimentón: 0.75 cucharadita", result)


if __name__ == "__main__":
    unittest.main()

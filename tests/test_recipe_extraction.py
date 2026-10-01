import json
import unittest
from tools import extract_recipe_text


class ExtractionTests(unittest.TestCase):
    def test_recipe_graph_precedes_navigation(self):
        html = '''<nav>Advertisements and navigation</nav><script type="application/ld+json">
        {"@graph": [{"@type":"WebSite","name":"Site"}, {"@type":["Recipe"],
        "name":"Sopa", "recipeYield":"2", "recipeIngredient":["300 g tomate"],
        "recipeInstructions":[{"@type":"HowToStep","text":"Cocer el tomate"}]}]}</script>'''
        result = json.loads(extract_recipe_text(html))
        self.assertEqual(result["name"], "Sopa")
        self.assertEqual(result["recipeIngredient"], ["300 g tomate"])
        self.assertNotIn("Advertisements", str(result))

    def test_malformed_metadata_falls_back_to_article(self):
        html = '<script type="application/ld+json">broken</script><div>Cookie text</div><article><p>Ingredientes: pan</p></article>'
        self.assertEqual(extract_recipe_text(html), "Ingredientes: pan")

    def test_recipe_sections_keep_steps_but_drop_image_metadata(self):
        recipe = {"@type": "Recipe", "recipeIngredient": ["pan"], "recipeInstructions": [
            {"@type": "HowToSection", "name": "Preparación", "itemListElement": [
                {"text": "<p>Tostar el pan.</p>", "image": "https://example.com/huge-image"},
                {"text": "Servir."},
            ]},
        ]}
        result = json.loads(extract_recipe_text('<script type="application/ld+json">' + json.dumps(recipe) + '</script>'))
        self.assertEqual(result["recipeInstructions"], ["Preparación", "Tostar el pan.", "Servir."])
        self.assertNotIn("huge-image", str(result))

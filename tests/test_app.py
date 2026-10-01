"""Offline UI journeys; credentials and model responses are fake."""
import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENROUTER_DEMO_MODEL": "openrouter/free"})
        self.env.start()
        self.builder = patch("agent.create_chef_agent", return_value=object())
        self.create = self.builder.start()
        self.streamer = patch("agent.stream_agent_response", return_value=iter([("text", "Una receta de prueba.")]))
        self.stream = self.streamer.start()

    def tearDown(self):
        self.streamer.stop()
        self.builder.stop()
        self.env.stop()

    def test_no_key_shows_landing_and_disabled_chat(self):
        app = AppTest.from_file("app.py").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.chat_input[0].disabled)
        self.assertTrue(any("Personal Chef" in x.value for x in app.markdown))
        self.create.assert_not_called()

    def test_demo_chat_and_quota_survive_new_conversation(self):
        os.environ["OPENROUTER_API_KEY"] = "fake-server-key"
        app = AppTest.from_file("app.py").run()
        self.assertFalse(app.exception)
        app.chat_input[0].set_value("Una sopa").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["demo_turns"], 1)
        self.assertEqual(app.session_state["messages"][-1]["content"], "Una receta de prueba.")
        self.assertTrue(self.stream.call_args.kwargs["callbacks"])
        app.button[0].click().run()
        self.assertEqual(app.session_state["messages"], [])
        self.assertEqual(app.session_state["demo_turns"], 1)
        app.session_state["demo_turns"] = 5
        app.run()
        self.assertTrue(app.chat_input[0].disabled)

    def test_custom_key_and_provider_switch_reset_history(self):
        os.environ["OPENROUTER_API_KEY"] = "fake-server-key"
        app = AppTest.from_file("app.py").run()
        app.chat_input[0].set_value("Hola").run()
        app.radio[0].set_value("Mi clave de OpenRouter").run()
        self.assertEqual(app.session_state["messages"], [])
        self.assertTrue(app.chat_input[0].disabled)
        app.text_input(key="key_openrouter").set_value("fake-user-key").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.chat_input[0].disabled)
        settings = self.create.call_args.args[0]
        self.assertEqual(settings.api_key, "fake-user-key")
        self.assertFalse(settings.demo)

    def test_invalid_paid_demo_is_disabled(self):
        os.environ.update(OPENROUTER_API_KEY="fake-key", OPENROUTER_DEMO_MODEL="paid/model")
        app = AppTest.from_file("app.py").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.chat_input[0].disabled)
        self.create.assert_not_called()

    def test_interrupted_answer_is_preserved_and_next_turn_recovers(self):
        import httpx
        os.environ["OPENROUTER_API_KEY"] = "fake-server-key"
        def broken_stream(*args, **kwargs):
            yield ("text", "Ingredientes: pan")
            raise httpx.ReadTimeout("fake-server-key private request")
        self.stream.side_effect = broken_stream
        app = AppTest.from_file("app.py").run()
        app.chat_input[0].set_value("hamburguesa").run()
        self.assertFalse(app.exception)
        reply = app.session_state["messages"][-1]["content"]
        self.assertIn("Respuesta incompleta", reply)
        self.assertIn("Ingredientes: pan", reply)
        self.assertIn("demasiado", reply)
        self.assertIn("Referencia:", reply)
        self.assertNotIn("fake-server-key", reply)
        self.assertNotIn("private request", reply)
        self.stream.side_effect = None
        self.stream.return_value = iter([("text", "Respuesta recuperada")])
        app.chat_input[0].set_value("hamburguesa").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["messages"][-1]["content"], "Respuesta recuperada")
        self.assertEqual(self.create.call_count, 2)

    def test_plan_progress_is_preserved_in_chat_history(self):
        os.environ["OPENROUTER_API_KEY"] = "fake-server-key"
        todos = [{"content": "Preparar compra", "status": "completed"}]
        self.stream.return_value = iter([("plan", todos), ("text", "Lista lista.")])
        app = AppTest.from_file("app.py").run()
        app.chat_input[0].set_value("Planifica cinco cenas").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["messages"][-1]["plan"], todos)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.expander[0].label, "Plan de trabajo")


if __name__ == "__main__":
    unittest.main()

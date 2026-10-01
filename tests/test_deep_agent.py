"""Run the actual Deep Agents graph offline with scripted model messages."""
import unittest
from unittest.mock import patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent import create_chef_agent, stream_agent_response, MAX_MODEL_CALLS
from providers import ModelSettings, DemoBudget, DemoLimitError


class ScriptedModel(BaseChatModel):
    model_name: str = "openrouter/free"
    replies: list[AIMessage]
    calls: int = 0
    tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "scripted"

    def _get_ls_params(self, **kwargs):
        return {"ls_provider": "openrouter", "ls_model_name": self.model_name}

    def bind_tools(self, tools, **kwargs):
        self.tool_names = [t.name if hasattr(t, "name") else t["name"] for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = self.replies[min(self.calls, len(self.replies) - 1)].model_copy(deep=True)
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=result)])


def call(name, args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


class DeepAgentTests(unittest.TestCase):
    def build(self, replies):
        model = ScriptedModel(replies=replies)
        with patch("agent.create_chat_model", return_value=model):
            graph = create_chef_agent(ModelSettings("openrouter", "fake"))
        return graph, model

    def test_plan_stream_shopping_and_session_isolation(self):
        todos = [{"content": "Preparar compra", "status": "in_progress"}]
        graph, model = self.build([
            call("write_todos", {"todos": todos}),
            call("scale_meal_plan", {"people_per_meal": 2, "meals": [{
                "meal": "Cena", "source_url": "https://example.com", "source_servings": 2,
                "servings_estimated": False, "ingredients": [
                {"ingredient": "tomate", "quantity": 200, "unit": "g", "estimated": True},
                {"ingredient": "tomate", "quantity": 300, "unit": "g", "estimated": False},
            ]}]}),
            AIMessage(content="Compra: 500 g de tomate (estimación)."),
        ])
        events = list(stream_agent_response(graph, "Planifica", "a"))
        self.assertIn(("plan", todos), events)
        self.assertTrue(any(e[0] == "text" and "500" in e[1] for e in events))
        self.assertNotIn("task", model.tool_names)
        self.assertNotIn("execute", model.tool_names)
        state = graph.get_state({"configurable": {"thread_id": "a"}}).values
        self.assertEqual(state["todos"], todos)
        self.assertTrue(any(m.type == "tool" and "500 g" in str(m.content) for m in state["messages"]))
        self.assertEqual(graph.get_state({"configurable": {"thread_id": "b"}}).values, {})

    def test_model_call_cap_stops_real_graph(self):
        from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
        graph, model = self.build([call("ls", {"path": "/"})])
        with self.assertRaises(ModelCallLimitExceededError):
            list(stream_agent_response(graph, "Continúa", "a"))
        self.assertEqual(model.calls, MAX_MODEL_CALLS)

    def test_demo_budget_propagates_into_real_graph(self):
        graph, model = self.build([call("ls", {"path": "/"}), AIMessage(content="Done")])
        with self.assertRaises(DemoLimitError):
            list(stream_agent_response(graph, "Hola", "a", [DemoBudget(daily_calls=1)]))
        self.assertEqual(model.calls, 1)

    def test_recipe_search_and_read_survive_migration(self):
        graph, model = self.build([
            call("web_search", {"query": "sopa"}),
            call("fetch_page", {"url": "https://example.com/sopa"}),
            AIMessage(content="Sopa: 300 g de tomate. Fuente: https://example.com/sopa"),
        ])
        with patch("tools._duckduckgo") as search, patch("tools.requests.get") as get:
            search.run.return_value = [{"title": "Sopa", "link": "https://example.com/sopa", "snippet": "Receta"}]
            get.return_value.text = "<article>Ingredientes: 300 g de tomate. Cocer.</article>"
            events = list(stream_agent_response(graph, "Sopa", "recipe"))
        starts = [e[1] for e in events if e[0] == "tool_start"]
        self.assertEqual(starts, ["web_search", "fetch_page"])
        self.assertTrue(any(e[0] == "text" and "example.com/sopa" in e[1] for e in events))

    def test_last_call_reserves_text_without_tools(self):
        graph, model = self.build([AIMessage(content="Resultado parcial")])
        # Exercise the middleware with the same ModelRequest shape used by LangChain.
        from langchain.agents.middleware.types import ModelRequest
        from langchain_core.messages import SystemMessage
        from agent import reserve_final_answer
        request = ModelRequest(model=model, messages=[], tools=[{"name": "web_search"}],
                               state={"run_model_call_count": MAX_MODEL_CALLS - 1},
                               system_message=SystemMessage(content="Chef"))
        observed = []
        reserve_final_answer.wrap_model_call(request, lambda r: observed.append(r))
        self.assertEqual(observed[0].tool_choice, "none")
        self.assertIn("última llamada", observed[0].system_message.content)

    def test_virtual_notes_do_not_touch_workspace_and_calls_reset_per_turn(self):
        with patch("agent.MAX_MODEL_CALLS", 2):
            graph, model = self.build([
                call("write_file", {"file_path": "/chef-test-note.txt", "content": "sin lactosa"}),
                AIMessage(content="Anotado"), AIMessage(content="Recordado"),
            ])
        list(stream_agent_response(graph, "Recuerda sin lactosa", "a"))
        state = graph.get_state({"configurable": {"thread_id": "a"}}).values
        self.assertIn("/chef-test-note.txt", state["files"])
        self.assertEqual(model.calls, 2)
        list(stream_agent_response(graph, "¿Lo recuerdas?", "a"))
        state = graph.get_state({"configurable": {"thread_id": "a"}}).values
        self.assertEqual(model.calls, 3)
        from pathlib import Path
        self.assertFalse(Path("chef-test-note.txt").exists())

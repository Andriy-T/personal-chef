import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from langchain_core.messages import AIMessageChunk, ToolMessage

from agent import create_chef_agent, stream_agent_response, GRAPH_STEP_LIMIT
from providers import (DemoBudget, DemoLimitError, ModelSettings, public_error,
                       IncompleteResponseError, record_failure)


class ProviderTests(unittest.TestCase):
    def test_demo_rejects_paid_and_other_provider(self):
        for provider, model in [("openrouter", "openai/gpt-4o"), ("openai", "x:free")]:
            with self.assertRaises(ValueError):
                ModelSettings(provider, "secret", model, demo=True)
        self.assertNotIn("secret", repr(ModelSettings("openrouter", "secret")))

    def test_explicit_routing_and_no_demo_retries(self):
        with patch("agent.ChatOpenRouter") as router, patch("agent.ChatOpenAI") as direct, patch("agent.create_deep_agent"):
            create_chef_agent(ModelSettings("openrouter", "router-key", demo=True))
            self.assertEqual(router.call_args.kwargs["api_key"], "router-key")
            self.assertEqual(router.call_args.kwargs["model"], "openrouter/free")
            self.assertEqual(router.call_args.kwargs["max_retries"], 0)
            self.assertEqual(router.call_args.kwargs["max_tokens"], 4096)
            sdk = router.call_args.kwargs["client"].sdk_configuration
            self.assertIsNone(sdk.retry_config)
            self.assertEqual(sdk.timeout_ms, 45_000)
            direct.assert_not_called()

    def test_budget_minute_day_reset_and_concurrency(self):
        now = [datetime(2026, 9, 26, tzinfo=timezone.utc)]
        budget = DemoBudget(daily_calls=2, minute_calls=1, clock=lambda: now[0])
        budget.on_chat_model_start({}, [])
        with self.assertRaises(DemoLimitError):
            budget.on_chat_model_start({}, [])
        now[0] += timedelta(seconds=61)
        budget.on_chat_model_start({}, [])
        now[0] += timedelta(seconds=61)
        with self.assertRaises(DemoLimitError):
            budget.on_chat_model_start({}, [])
        now[0] += timedelta(days=1)
        budget.on_chat_model_start({}, [])

        shared = DemoBudget(daily_calls=4, minute_calls=4)
        def attempt(_):
            try:
                shared.on_chat_model_start({}, [])
                return 1
            except DemoLimitError:
                return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(20))), 4)

    def test_callback_stops_model_before_request(self):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        model = FakeListChatModel(responses=["first", "second"])
        budget = DemoBudget(daily_calls=1)
        model.invoke("hello", config={"callbacks": [budget]})
        with self.assertRaises(DemoLimitError):
            model.invoke("hello again", config={"callbacks": [budget]})
        self.assertEqual(model.i, 1)

    def test_errors_hide_raw_content(self):
        self.assertNotIn("secret", public_error(RuntimeError("secret credential and prompt")))
        error = RuntimeError("secret")
        error.status_code = 429
        self.assertIn("cuota", public_error(error))

    def test_timeout_and_step_limit_are_distinct(self):
        import httpx
        from langgraph.errors import GraphRecursionError
        self.assertIn("demasiado", public_error(httpx.ReadTimeout("secret")))
        self.assertIn("límite de pasos", public_error(GraphRecursionError("secret")))

    def test_diagnostics_omit_exception_payload(self):
        with self.assertLogs("personal_chef", level="WARNING") as captured:
            reference = record_failure(RuntimeError("secret-key private-prompt"), "openrouter", "openrouter/free", "model")
        message = captured.output[0]
        self.assertIn(reference, message)
        self.assertIn("type=RuntimeError", message)
        self.assertNotIn("secret-key", message)
        self.assertNotIn("private-prompt", message)

    def test_truncated_stream_is_not_reported_as_complete(self):
        class Graph:
            def stream(self, *args, **kwargs):
                yield "messages", (AIMessageChunk(content="Partial", response_metadata={"finish_reason": "length"}), {"langgraph_node": "model"})
        events = stream_agent_response(Graph(), "hello", "thread")
        self.assertEqual(next(events), ("text", "Partial"))
        with self.assertRaises(IncompleteResponseError):
            next(events)

    def test_raw_tool_protocol_is_not_a_successful_answer(self):
        class Graph:
            def stream(self, *args, **kwargs):
                for text in ["<tool_", "call>write_todos" + "x" * 500]:
                    yield "messages", (AIMessageChunk(content=text), {"langgraph_node": "model"})
        with self.assertRaises(IncompleteResponseError) as caught:
            list(stream_agent_response(Graph(), "menu", "thread"))
        self.assertEqual(caught.exception.reason, "protocol")

    def test_stream_normalizes_content_and_passes_limits(self):
        class Graph:
            def stream(self, data, config, stream_mode):
                self.config = config
                yield "messages", (AIMessageChunk(content="", tool_calls=[{"name": "web_search", "args": {"query": "sopa"}, "id": "a"}]), {"langgraph_node": "model"})
                yield "messages", (ToolMessage(content="source", tool_call_id="a"), {"langgraph_node": "tools"})
                yield "messages", (AIMessageChunk(content=[{"type": "text", "text": "Sopa"}]), {"langgraph_node": "model"})
        graph = Graph()
        budget = DemoBudget()
        events = list(stream_agent_response(graph, "sopa", "session-a", [budget]))
        self.assertEqual(events[-1], ("text", "Sopa"))
        self.assertEqual(events[1], ("tool_end", "web_search"))
        self.assertEqual(graph.config["callbacks"], [budget])
        self.assertEqual(graph.config["recursion_limit"], GRAPH_STEP_LIMIT)


if __name__ == "__main__":
    unittest.main()

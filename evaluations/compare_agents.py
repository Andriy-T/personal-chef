"""Opt-in live comparison using only the configured free OpenRouter model.

Run each engine separately; see evaluations/RESULTS.md.
Writes public test prompts, answers and tool evidence; never credentials.
This is a small diagnostic comparison, not a benchmark proving superiority.
"""
import json
import argparse
import os
import traceback
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent import create_chat_model, create_chef_agent, stream_agent_response
from providers import ModelSettings, DemoBudget, error_kind, EmptyResponseError
from tools import web_search, fetch_page, get_ingredient_substitutes, create_meal_plan

PROMPT = "Planifica cinco cenas vegetarianas para dos personas, sin berenjena. Reutiliza ingredientes entre días y prepara una lista de compra consolidada con cantidades para las diez raciones. Busca y lee fuentes, enlázalas y distingue las cantidades estimadas. Sé breve."


class Metrics(BaseCallbackHandler):
    def __init__(self):
        self.calls = 0
        self.tools = []
        self.models = set()

    def on_chat_model_start(self, *args, **kwargs):
        self.calls += 1

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.tools.append({"name": serialized.get("name"), "input": input_str})

    def on_llm_end(self, response, **kwargs):
        for group in response.generations:
            for generation in group:
                metadata = getattr(generation, "message", None)
                if metadata:
                    name = metadata.response_metadata.get("model_name") or metadata.response_metadata.get("model")
                    if name:
                        self.models.add(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Free model ID; paid IDs are rejected.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--engine", choices=["baseline", "deepagents"], required=True,
                        help="Run separately, at least one minute apart, to respect shared free quotas.")
    args = parser.parse_args()
    output_name = args.output or f"{args.engine}_comparison.json"
    if Path(output_name).name != output_name:
        parser.error("--output must be a filename, not a path")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = ModelSettings("openrouter", os.environ["OPENROUTER_API_KEY"], args.model or os.getenv("OPENROUTER_DEMO_MODEL", "openrouter/free"), demo=True)
    budget = DemoBudget(daily_calls=16, minute_calls=10)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "prompt": PROMPT,
              "configured_model": settings.model, "runs": []}
    if args.engine == "baseline":
        graph = create_react_agent(
            create_chat_model(settings), tools=[web_search, fetch_page, get_ingredient_substitutes, create_meal_plan],
            prompt=Path(__file__).with_name("baseline_prompt.txt").read_text(encoding="utf-8"),
            checkpointer=InMemorySaver(),
        )
    else:
        graph = create_chef_agent(settings)
    for name, graph in [(args.engine, graph)]:
        metrics = Metrics()
        start = perf_counter()
        thread_id = uuid4().hex
        answer, plans, error = "", [], None
        try:
            for event in stream_agent_response(graph, PROMPT, thread_id, [budget, metrics], step_limit=10 if name == "baseline" else 100):
                if event[0] == "text":
                    answer += event[1]
                elif event[0] == "plan":
                    plans.append(event[1])
                elif event[0] == "tool_start":
                    print(name, event[1], flush=True)
            if not answer.strip():
                raise EmptyResponseError()
        except Exception as exc:
            error = {"kind": error_kind(exc), "type": type(exc).__name__}
            error["frames"] = [f"{frame.name}:{frame.lineno}" for frame in traceback.extract_tb(exc.__traceback__)[-5:]]
            # This runner uses only the public fixed test prompt. Retain a bounded
            # redacted diagnostic; the application never logs exception payloads.
            error["detail"] = str(exc).replace(settings.api_key, "[redacted]")[:600]
            if hasattr(exc, "reason"):
                error["reason"] = exc.reason
        state = graph.get_state({"configurable": {"thread_id": thread_id}}).values
        tool_results = [{"name": m.name, "tool_call_id": m.tool_call_id, "content": m.content}
                        for m in state.get("messages", []) if m.type == "tool"]
        tool_calls = [call for m in state.get("messages", []) for call in getattr(m, "tool_calls", [])]
        run = {"engine": name, "seconds": round(perf_counter() - start, 2), "model_calls": metrics.calls,
               "resolved_models": sorted(metrics.models), "tools": metrics.tools, "plans": plans,
               "answer": answer, "error": error, "tool_calls": tool_calls, "tool_results": tool_results}
        report["runs"].append(run)
        Path(__file__).with_name(output_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(name, run["seconds"], "seconds", metrics.calls, "calls", error, flush=True)
    return 1 if any(run["error"] for run in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

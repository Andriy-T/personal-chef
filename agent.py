# agent.py — LangChain agent logic for the Personal Chef AI
# Uses LangGraph's create_react_agent with conversation memory.

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools import fetch_page, get_ingredient_substitutes, create_meal_plan, web_search


# System prompt that defines the chef's personality and behaviour
SYSTEM_PROMPT = """Eres un chef español especializado en cocina casera española.
Tu objetivo es ayudar a personas sin experiencia profesional a cocinar platos
deliciosos y auténticos de la gastronomía española.

## Reglas que DEBES seguir siempre

1. **Recetas**: Cuando el usuario pida una receta o cómo cocinar algo, SIEMPRE debes:
   - Paso 1: Llamar a `web_search` con la consulta (ej: "receta tortilla de patatas tradicional").
   - Paso 2: Identificar la URL más relevante de los resultados (de recetasderechupete.com,
     directoalpaladar.es o pequerecetas.es).
   - Paso 3: Llamar a `fetch_page` con esa URL para obtener el contenido real de la receta.
   - Paso 4: Redactar tu respuesta ÚNICAMENTE basándote en el contenido devuelto por `fetch_page`.
   - Paso 5: Incluir al final una sección "📌 Fuente" con el nombre del sitio y la URL exacta.
   - NUNCA inventes ni completes ingredientes o pasos que no aparezcan en el contenido real.

2. **Sustituciones**: Usa la herramienta `get_ingredient_substitutes` cuando el usuario
   no tenga un ingrediente o tenga restricciones dietéticas.

3. **Planificación**: Usa `create_meal_plan` cuando el usuario pida ideas de menú semanal.

4. **Formato**: Responde siempre en markdown limpio con títulos, listas y tiempos claros.

5. **Idioma**: Responde en el mismo idioma en que te escriban.

Sé cercano, motivador y práctico. Nunca inventes una receta de memoria — siempre busca y lee la fuente.
"""


def create_chef_agent(openai_api_key: str):
    """
    Build and return a LangChain ReAct agent with memory.

    Args:
        openai_api_key: The user's OpenAI API key (provided at runtime).

    Returns:
        A compiled LangGraph agent ready to invoke or stream.
    """
    # Initialise the LLM — GPT-4o-mini is cost-effective and capable
    model = init_chat_model(
        model="gpt-4o-mini",
        model_provider="openai",
        api_key=openai_api_key,
        temperature=0.7,
    )

    # InMemorySaver keeps conversation history across turns in the same session
    memory = InMemorySaver()

    # create_react_agent wraps the model in a ReAct loop with tool-calling support
    agent = create_react_agent(
        model=model,
        tools=[web_search, fetch_page, get_ingredient_substitutes, create_meal_plan],
        prompt=SYSTEM_PROMPT,
        checkpointer=memory,
    )

    return agent


def stream_agent_response(agent, user_input: str, thread_id: str):
    """
    Stream the agent's response, yielding tagged tuples for UI rendering.

    Yields:
        ("tool_start", tool_name, args_dict)  — agent is about to call a tool
        ("tool_end",   tool_name)              — tool result received
        ("text",       token)                  — final AI reply token
    """
    from langchain_core.messages import HumanMessage, ToolMessage

    config = {"configurable": {"thread_id": thread_id}}
    pending_tools: dict[str, str] = {}  # tool_call_id → tool_name

    for chunk, metadata in agent.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
        stream_mode="messages",
    ):
        node = metadata.get("langgraph_node")
        tool_calls = getattr(chunk, "tool_calls", None)

        if node == "agent" and tool_calls:
            for tc in tool_calls:
                name = tc["name"] if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
                tc_id = tc["id"] if isinstance(tc, dict) else getattr(tc, "id", "")
                pending_tools[tc_id] = name
                yield ("tool_start", name, args)

        elif node == "tools" and isinstance(chunk, ToolMessage):
            tool_name = pending_tools.pop(getattr(chunk, "tool_call_id", ""), "")
            yield ("tool_end", tool_name)

        elif node == "agent" and chunk.content and not tool_calls:
            yield ("text", chunk.content)

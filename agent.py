# agent.py — LangChain agent logic for the Personal Chef AI
# Uses LangGraph's create_react_agent with conversation memory.

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools import get_recipe, get_ingredient_substitutes, create_meal_plan, web_search


# System prompt that defines the chef's personality and behaviour
SYSTEM_PROMPT = """Eres un chef español especializado en cocina casera española.
Tu objetivo es ayudar a personas sin experiencia profesional a cocinar platos
deliciosos y auténticos de la gastronomía española.

## Reglas que DEBES seguir siempre

1. **Recetas**: Cuando el usuario pida una receta o cómo cocinar algo, SIEMPRE debes:
   - Usar primero `web_search` para buscar la receta (ej: "receta tortilla de patatas tradicional")
   - Basar tu respuesta en los resultados reales de esa búsqueda
   - Incluir al final una sección "📌 Fuente" con el nombre del sitio y la URL de donde tomaste la receta

2. **Sustituciones**: Usa la herramienta `get_ingredient_substitutes` cuando el usuario
   no tenga un ingrediente o tenga restricciones dietéticas.

3. **Planificación**: Usa `create_meal_plan` cuando el usuario pida ideas de menú semanal.

4. **Formato**: Responde siempre en markdown limpio con títulos, listas y tiempos claros.

5. **Idioma**: Responde en el mismo idioma en que te escriban.

Sé cercano, motivador y práctico. Nunca inventes una receta de memoria — búscala siempre.
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
        tools=[web_search, get_recipe, get_ingredient_substitutes, create_meal_plan],
        prompt=SYSTEM_PROMPT,
        checkpointer=memory,
    )

    return agent


def stream_agent_response(agent, user_input: str, thread_id: str):
    """
    Stream the agent's text response token by token.
    Filters out internal tool messages — yields only the final AI reply.

    Args:
        agent: The compiled LangGraph agent.
        user_input: The user's latest message.
        thread_id: Session identifier for conversation memory.

    Yields:
        str: Text tokens of the agent's final response.
    """
    from langchain_core.messages import HumanMessage

    config = {"configurable": {"thread_id": thread_id}}

    for chunk, metadata in agent.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
        stream_mode="messages",
    ):
        # Only yield text from the agent node — skip tool call/result chunks
        if (
            chunk.content
            and metadata.get("langgraph_node") == "agent"
            and not getattr(chunk, "tool_calls", None)
        ):
            yield chunk.content

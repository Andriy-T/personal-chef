"""Provider settings and conservative, process-local demo quotas."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
import logging
import traceback
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler

DEFAULT_ROUTER_MODEL = "openrouter/free"
DEFAULT_OPENAI_MODEL = "gpt-5.4-nano"
DEMO_SESSION_TURNS = 5
MAX_INPUT_CHARS = 4000


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    api_key: str = field(repr=False)
    model: str = DEFAULT_ROUTER_MODEL
    demo: bool = False

    def __post_init__(self):
        if self.provider not in {"openrouter", "openai"}:
            raise ValueError("Proveedor no compatible.")
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("Falta la clave o el modelo.")
        if self.demo and (
            self.provider != "openrouter"
            or not (self.model == DEFAULT_ROUTER_MODEL or self.model.endswith(":free"))
        ):
            raise ValueError("La demo solo admite modelos gratuitos de OpenRouter.")


class DemoLimitError(RuntimeError):
    pass


class EmptyResponseError(RuntimeError):
    pass


class IncompleteResponseError(RuntimeError):
    def __init__(self, reason="unknown"):
        self.reason = reason if reason in {"length", "error", "content_filter", "protocol"} else "unknown"
        super().__init__(self.reason)


def error_kind(error):
    """Classify without parsing or exposing possibly sensitive exception messages."""
    names = {cls.__name__ for cls in type(error).__mro__}
    if isinstance(error, DemoLimitError):
        return "demo_limit"
    if isinstance(error, EmptyResponseError):
        return "empty_response"
    if isinstance(error, IncompleteResponseError):
        return "incomplete_response"
    if names & {"GraphRecursionError", "ModelCallLimitExceededError"}:
        return "step_limit"
    if names & {"TimeoutError", "TimeoutException", "APITimeoutError"}:
        return "timeout"
    status = getattr(error, "status_code", None)
    if status in (401, 403):
        return "authentication"
    if status in (402, 429):
        return "provider_quota"
    if isinstance(status, int) and status >= 500:
        return "provider_unavailable"
    if names & {"APIConnectionError", "NetworkError", "ConnectError"}:
        return "connection"
    return "unknown"


def record_failure(error, provider, model, stage):
    """Log structural metadata only: no exception text, prompts, URLs or keys."""
    reference = uuid4().hex[:12]
    frames = traceback.extract_tb(error.__traceback__)
    location = ",".join(f"{f.name}:{f.lineno}" for f in frames[-5:])
    # Provider/model/stage are caller-supplied; cap and strip control characters.
    def safe(value):
        return "".join(c for c in str(value) if c.isalnum() or c in "_./:-")[:100]
    logging.getLogger("personal_chef").warning(
        "failure ref=%s kind=%s type=%s provider=%s model=%s stage=%s frames=%s",
        reference, error_kind(error), type(error).__name__, safe(provider),
        safe(model), safe(stage), location,
    )
    return reference


class DemoBudget(BaseCallbackHandler):
    """Count actual model starts across sessions, including failed attempts.

    Cached once per Streamlit process. This is not a durable or distributed quota;
    provider limits remain authoritative. No prompts or credentials are retained.
    """

    raise_error = True

    def __init__(self, daily_calls=40, minute_calls=10, clock=None):
        self.daily_calls = daily_calls
        self.minute_calls = minute_calls
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()
        self._day = None
        self._used = 0
        self._recent = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        with self._lock:
            now = self._clock()
            if self._day != now.date():
                self._day, self._used = now.date(), 0
            self._recent = [t for t in self._recent if (now - t).total_seconds() < 60]
            if self._used >= self.daily_calls:
                raise DemoLimitError("La demo ha agotado su cupo de hoy. Puedes usar tu propia clave.")
            if len(self._recent) >= self.minute_calls:
                raise DemoLimitError("La demo está ocupada. Espera un minuto y vuelve a intentarlo.")
            self._used += 1
            self._recent.append(now)


def public_error(error):
    """Never expose SDK exceptions, which can contain request data or secrets."""
    if isinstance(error, DemoLimitError):
        return str(error)
    return {
        "authentication": "No se ha podido autenticar con el proveedor. Revisa la clave configurada.",
        "provider_quota": "El proveedor no tiene cuota disponible. Inténtalo más tarde o usa otra clave.",
        "timeout": "El proveedor ha tardado demasiado en responder. Vuelve a intentarlo en unos momentos.",
        "provider_unavailable": "El proveedor está temporalmente indisponible. Vuelve a intentarlo en unos momentos.",
        "connection": "Se ha perdido la conexión con el proveedor. Vuelve a intentarlo en unos momentos.",
        "step_limit": "No he podido completar la receta dentro del límite de pasos de esta consulta. Prueba con una petición más concreta.",
        "empty_response": "El modelo no ha devuelto una respuesta de texto. Vuelve a intentarlo o selecciona otro modelo.",
        "incomplete_response": "La respuesta del modelo se ha interrumpido o ha alcanzado su límite de generación. Puedes volver a intentarlo.",
    }.get(error_kind(error), "No se ha podido completar la respuesta. Inténtalo de nuevo o cambia de modelo.")

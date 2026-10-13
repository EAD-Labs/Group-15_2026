"""Intervention fidelity - what each turn actually delivered.

Carroll et al. (2007): implementation fidelity is whether an intervention is
delivered as intended. For Story Studio that means: did the participant get the
model, provider and role their condition specifies, or did something
substitute for it? Before this, three substitutions were silent:

  - the reply fell back to the offline scaffold when the model failed;
  - Gemini walked its fallback chain to a different model on a quota error;
  - the classifier and Monitor fell back to keyword rules.

Every turn now carries a `fidelity` record, one entry per LLM call:

  {"calls": {"classifier": {...}, "monitor": {...}, "response": {...}},
   "intended": bool,      # the reply came from the requested provider + model
   "degraded": [...]}     # human-readable list of every substitution

Each call entry: requested_provider, requested_model, provider, model,
status (ok | substituted_model | fallback | failed | rules), error.
"""
from .state import TurnState


def record(state: TurnState, call: str, *, requested_provider: str,
           requested_model: str, provider: str = "", model: str = "",
           status: str = "ok", error: str = "") -> None:
    if status == "ok" and model and requested_model and model != requested_model:
        # Gemini's quota chain answered from a sibling model.
        status = "substituted_model"
    state.fidelity.setdefault("calls", {})[call] = {
        "requested_provider": requested_provider,
        "requested_model": requested_model,
        "provider": provider,
        "model": model,
        "status": status,
        **({"error": error[:200]} if error else {}),
    }
    summarise(state)


def summarise(state: TurnState) -> None:
    calls = state.fidelity.get("calls", {})
    degraded = [
        f"{name}: {c['status']}"
        + (f" ({c['requested_model']} -> {c['model']})" if c["status"] == "substituted_model" else "")
        for name, c in calls.items() if c["status"] != "ok"
    ]
    response = calls.get("response")
    state.fidelity["intended"] = bool(response) and response["status"] == "ok"
    state.fidelity["degraded"] = degraded

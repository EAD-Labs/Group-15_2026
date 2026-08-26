"""Graph runner.

The topology is declared as data so the interface can draw it and so each turn
can report which path it actually took. Swapping this for a real LangGraph
StateGraph is a mechanical change: same nodes, same state object.
"""
from .nodes import (
    agency_enforcer,
    guardrail_verifier,
    intent_classifier,
    response_formatter,
    socratic_engine,
)
from .state import TurnState

GRAPH_SPEC = [
    {"id": "intent_classifier", "label": "Intent Classifier",
     "desc": "Helsinki help-seeking category", "next": ["guardrail_verifier"]},
    {"id": "guardrail_verifier", "label": "Guardrail Verifier",
     "desc": "Intercept executive help-seeking", "next": ["socratic_engine"]},
    {"id": "socratic_engine", "label": "Socratic Engine",
     "desc": "Question generation via LLM", "next": ["response_formatter"]},
    {"id": "response_formatter", "label": "Formatter",
     "desc": "Parse response and probes", "next": ["agency_enforcer"]},
    {"id": "agency_enforcer", "label": "Agency Enforcer",
     "desc": "Strip any leaked narrative prose", "next": []},
]

_PIPELINE = [
    intent_classifier,
    guardrail_verifier,
    socratic_engine,
    response_formatter,
    agency_enforcer,
]


async def run_turn(state: TurnState) -> TurnState:
    for node in _PIPELINE:
        state = await node(state)
    return state

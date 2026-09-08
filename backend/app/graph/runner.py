"""Graph runner.

The topology is declared as data so the interface can draw it and so each turn
can report which path it actually took. Swapping this for a real LangGraph
StateGraph is a mechanical change: same nodes, same state object.
"""
from .nodes import (
    agency_enforcer,
    role_arbiter,
    intent_classifier,
    response_formatter,
    response_engine,
)
from .state import TurnState

GRAPH_SPEC = [
    {"id": "intent_classifier", "label": "Intent Classifier",
     "desc": "Helsinki help-seeking category", "next": ["role_arbiter"]},
    {"id": "role_arbiter", "label": "Role Arbiter",
     "desc": "Resolve role × activity × intent", "next": ["response_engine"]},
    {"id": "response_engine", "label": "Response Engine",
     "desc": "Generate response via LLM", "next": ["response_formatter"]},
    {"id": "response_formatter", "label": "Formatter",
     "desc": "Parse response and probes", "next": ["agency_enforcer"]},
    {"id": "agency_enforcer", "label": "Agency Enforcer",
     "desc": "Check output against role contract", "next": []},
]

_PIPELINE = [
    intent_classifier,
    role_arbiter,
    response_engine,
    response_formatter,
    agency_enforcer,
]


async def run_turn(state: TurnState) -> TurnState:
    for node in _PIPELINE:
        state = await node(state)
    return state

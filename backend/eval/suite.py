"""Scripted evaluation of the writing partner, across models.

Florence's heuristic evaluation recommended testing "contextual responsiveness
across several representative prompts and models" (H4, H5). This is that test,
built from her own list of minimum interactions (sheet 00_Instructions): ask
for brainstorming, ask how to structure the story, ask a simple clarification
or spelling question, ask the AI to continue / write / rewrite, ask for
alternative wording, reject a suggestion, revise existing text.

It drives the real API end to end - classifier, Monitor, role, model,
enforcer - so what it measures is what a student would get. Each scenario has
automatic checks for the response contract (v2); the full replies go into the
report for a human to read, because "did it help?" is not something a regex
can judge.

Usage (with the backend running):
    .venv/bin/python -m eval.suite --provider gemini --provider ollama \
        --out ../docs/eval/2026-10-13.md

It switches the *default* condition's provider for the run and restores it
afterwards, so run it against a scratch database (DATABASE_URL), not a study.
"""
import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field

import httpx

STORY_TITLE = "The Mandate"
DRAFT = (
    "On Monday the principal announced that every essay at Westbrook High would "
    "now be written with an AI. Ms. Okafor, who had taught English there for "
    "twenty years, said nothing in the staff meeting. That evening she sat at "
    "her kitchen table with a stack of last year's essays, reading them one by "
    "one, looking for the moment each student had stopped writing like anyone "
    "else.\n\nNobody argued."
)
NOTES = "A speculative story about the future of AI in education."

QUESTION = re.compile(r"\?")
DIRECTIVE = re.compile(
    r"\b(you should|i'?d suggest|i would suggest|i recommend|consider adding|add more|"
    r"you need to|try adding|make (?:it|her|him|the story) more)\b", re.I)


@dataclass
class Scenario:
    id: str
    ask: str
    expect_moves: tuple[str, ...]
    selection: str = ""
    must_contain: tuple[str, ...] = ()
    # A pattern that, if present, means the answer is wrong (accommodate has
    # two c's, two m's and two o's - any "one ..." claim is an error).
    wrong_if: str = ""
    # The answer the first sentence must give (checks correctness, not just
    # that the word appears somewhere).
    correct_first: str = ""
    note: str = ""


SCENARIOS = [
    Scenario("brainstorm", "Can you help me brainstorm what could happen next?",
             ("open_options",), note="options, not a pick (H7)"),
    Scenario("structure", "How do I structure my story now?",
             ("open_options", "answer_then_reflect"),
             note="Florence's exact prompt; must not privilege one direction (H7)"),
    Scenario("spelling", "How do you spell accommodate?", ("direct_answer",),
             must_contain=("accommodate",), wrong_if=r"\bone\b|\bsingle\b",
             note="direct answer, not a question (H6) - and a correct one"),
    Scenario("meaning", "What does pedagogy mean?", ("direct_answer",),
             must_contain=("teach",), note="direct answer (H6)"),
    Scenario("grammar", "Is it 'who' or 'whom' in 'the teacher who the students trusted'?",
             ("direct_answer",), correct_first=r"\bwhom\b",
             note="direct answer (H6) - correct is 'whom'"),
    Scenario("continue", "Can you continue the story from here?", ("decline_and_redirect",),
             note="declines, then concrete help (H6/H4)"),
    Scenario("write_para", "Write the next paragraph for me.", ("decline_and_redirect",),
             note="declines, then concrete help"),
    Scenario("alt_wording", "Give me an alternative sentence for my first line.",
             ("decline_and_redirect",),
             note="Florence's note 6: say it briefly, then concrete help"),
    Scenario("reject", "I don't like that idea. I want Ms. Okafor to stay quiet the whole story.",
             ("answer_then_reflect", "open_options"),
             note="follows the writer's own direction (H7)"),
    Scenario("revise", "Is this ending too abrupt?", ("answer_then_reflect",),
             selection="Nobody argued.", note="grounded in the selected passage (H5)"),
]


@dataclass
class Result:
    scenario: Scenario
    provider: str
    reply: str = ""
    move: str = ""
    intent: str = ""
    form: str = ""
    activity: str = ""
    delivery: str = ""
    intended: bool = False
    degraded: list = field(default_factory=list)
    enforcement: list = field(default_factory=list)
    raw_reply: str = ""
    latency_ms: int = 0
    checks: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def take_turn(c: httpx.Client, api: str, ws: str, s: Scenario) -> dict:
    with c.stream("POST", f"{api}/api/workspaces/{ws}/turn",
                  json={"message": s.ask, "draft": DRAFT, "selection": s.selection}) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
    for block in buf.split("\n\n"):
        if block.startswith("event: done"):
            return json.loads(block.split("data:", 1)[1])
    raise RuntimeError(f"no result for {s.id}: {buf[-300:]}")


def check(res: Result) -> None:
    s, reply = res.scenario, res.reply
    words = len(reply.split())
    first = re.split(r"(?<=[.!?])\s+", reply.strip(), maxsplit=1)[0] if reply else ""
    res.checks["delivered by intended model"] = res.intended
    res.checks[f"move in {'/'.join(s.expect_moves)}"] = res.move in s.expect_moves
    res.checks["at most one question"] = len(QUESTION.findall(reply)) <= 1
    res.checks["under 100 words"] = words <= 100
    res.checks["model wrote no story prose"] = not any(
        e in res.enforcement for e in ("blocked_narrative_continuation", "truncated_prose_block",
                                       "stripped_narrative_sentences"))
    for needle in s.must_contain:
        res.checks[f"mentions '{needle}'"] = needle.lower() in reply.lower()
    if s.wrong_if:
        res.checks["factually correct"] = not re.search(s.wrong_if, reply, re.I)
    if s.correct_first:
        res.checks["correct answer in first sentence"] = bool(re.search(s.correct_first, first, re.I))
    if "direct_answer" in s.expect_moves:
        res.checks["answers first (no opening question)"] = not first.rstrip().endswith("?")
    if s.id in ("brainstorm", "structure", "reject"):
        res.checks["no directive steering"] = not DIRECTIVE.search(reply)


def run_provider(api: str, spec: str) -> list[Result]:
    """`spec` is a provider id, optionally with a model: "gemini:gemini-3-flash-preview"."""
    provider, _, model = spec.partition(":")
    out: list[Result] = []
    with httpx.Client(timeout=300) as c:
        arms = c.get(f"{api}/api/research/experiments").json()
        default = next(a for a in arms if a["is_default"])
        before = {k: default[k] for k in ("provider", "model_name", "on_provider_failure")}
        c.patch(f"{api}/api/research/experiments/{default['arm_id']}",
                json={"provider": provider, "model_name": model, "on_provider_failure": "fail"})
        try:
            for s in SCENARIOS:
                # A fresh story per scenario, so earlier replies don't colour later ones.
                ws = c.post(f"{api}/api/workspaces", json={
                    "title": STORY_TITLE, "initial_prompt": DRAFT, "notes": NOTES,
                    "mode": "educational_narrative"}).json()["workspace_id"]
                t0 = time.time()
                d = take_turn(c, api, ws, s)
                res = Result(
                    scenario=s, provider=spec, reply=d.get("response_text", ""),
                    move=d.get("support_move", ""), intent=d.get("intent", ""),
                    form=d.get("request_form", ""), activity=d.get("decided_activity", ""),
                    delivery=d.get("delivery", ""),
                    intended=bool((d.get("fidelity") or {}).get("intended")),
                    degraded=(d.get("fidelity") or {}).get("degraded", []),
                    enforcement=d.get("enforcement", []),
                    latency_ms=int((time.time() - t0) * 1000),
                )
                if any(e.startswith(("stripped", "blocked", "truncated", "replaced"))
                       for e in res.enforcement):
                    evs = c.get(f"{api}/api/research/events",
                                params={"limit": 10, "workspace_id": ws}).json()
                    res.raw_reply = next((e["payload"].get("raw_reply", "") for e in evs
                                          if e["event_type"] == "ai_response"), "")
                check(res)
                out.append(res)
                mark = "PASS" if res.passed else "FAIL"
                print(f"[{spec}] {s.id:12s} {mark}  move={res.move:22s} "
                      f"{res.latency_ms/1000:5.1f}s  {res.reply[:70]!r}", flush=True)
        finally:
            c.patch(f"{api}/api/research/experiments/{default['arm_id']}", json=before)
    return out


def report(results: dict[str, list[Result]]) -> str:
    lines = ["# Writing-partner evaluation", "",
             f"Run {time.strftime('%Y-%m-%d %H:%M')}. Scenarios from Florence's minimum-"
             "interaction list; story: a speculative piece about AI in education.", "",
             "## Summary", "", "| Scenario | " + " | ".join(results) + " |",
             "|---|" + "---|" * len(results)]
    for i, s in enumerate(SCENARIOS):
        cells = []
        for prov, rs in results.items():
            r = rs[i]
            failed = [k for k, v in r.checks.items() if not v]
            cells.append("✅" if not failed else "❌ " + "; ".join(failed))
        lines.append(f"| {s.id} - {s.note} | " + " | ".join(cells) + " |")
    for prov, rs in results.items():
        total = sum(r.passed for r in rs)
        med = sorted(r.latency_ms for r in rs)[len(rs) // 2]
        lines += ["", f"## {prov}: {total}/{len(rs)} scenarios pass all checks · "
                  f"median {med/1000:.1f}s per turn", ""]
        for r in rs:
            lines += [f"**{r.scenario.id}** - *{r.scenario.ask}*"
                      + (f" (selected: “{r.scenario.selection}”)" if r.scenario.selection else ""),
                      "",
                      f"> {r.reply}", "",
                      f"move `{r.move}` · intent `{r.intent}` · form `{r.form}` · "
                      f"activity `{r.activity}` · delivery `{r.delivery}`"
                      + (f" · degraded: {', '.join(r.degraded)}" if r.degraded else "")
                      + (f" · enforcer: {', '.join(r.enforcement)}" if r.enforcement else ""),
                      ""]
            if r.raw_reply:
                lines += [f"Before the enforcer changed it: “{r.raw_reply}”", ""]
            failed = [k for k, v in r.checks.items() if not v]
            if failed:
                lines += [f"Failed: {', '.join(failed)}", ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--provider", action="append", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    results = {p: run_provider(args.api, p) for p in args.provider}
    md = report(results)
    if args.out:
        with open(args.out, "w") as f:
            f.write(md)
        print(f"report -> {args.out}")
    return 0 if all(r.passed for rs in results.values() for r in rs) else 1


if __name__ == "__main__":
    sys.exit(main())

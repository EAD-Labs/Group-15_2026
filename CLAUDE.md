# Story Studio — ET 617 Group 15

Human–AI co-creative storytelling prototype. See `README.md` for what it does
and how to run it (`./run.sh`).

## Current work

**`docs/iteration-2-plan.md` is the active plan.** Read it before making
architectural changes. It covers the client's requested next iteration —
activity-conditioned behaviour (Flower & Hayes) and configurable AI roles
(Steinhoff & Lehnen's Ghost/Partner/Tutor model) — as four phases, with the
literature grounding, open questions, and a register of known defects.

Conventions that are easy to violate by accident:

- **Writing activities are never a sequence.** No stepper, no ordering, no
  "current phase" indicator, no completion state. Flower & Hayes are explicit
  that the processes are embedded and recursive.
- **The student side is two panels: story and chat.** No controls over model,
  scaffold or writing activity, no metrics shown. Research instrumentation stays
  server-side and in the researcher portal (plan §8 D5).
- **The system decides the writing activity** (`backend/app/graph/monitor.py`,
  F&H's Monitor): an LLM judges from context, a rule is the fallback. Changing
  the prompt means bumping `MONITOR_PROMPT_VERSION`; the weights,
  `MONITOR_VERSION`.
- **Roles and arms are append-only on edit.** Editing in place destroys the
  ability to trace a turn back to the prompt that produced it. See defect D1.

## Source PDFs

Gitignored (`*.pdf`) — ACM copyright, and the HLD carries client contact
details. Cite by DOI. The three that matter are listed in §7.1 of the plan.

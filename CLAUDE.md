# Story Studio — ET 617 Group 15

Human–AI co-creative storytelling prototype. See `README.md` for what it does
and how to run it (`./run.sh`).

## Current work

**`docs/iteration-2-plan.md` is the active plan.** Read it before making
architectural changes. It covers the client's requested next iteration —
activity-conditioned behaviour (Flower & Hayes) and configurable AI roles
(Steinhoff & Lehnen's Ghost/Partner/Tutor model) — as four phases, with the
literature grounding, open questions, and a register of known defects.

Two conventions from that plan that are easy to violate by accident:

- **Writing activities are never a sequence.** No stepper, no ordering, no
  "current phase" indicator, no completion state. Flower & Hayes are explicit
  that the processes are embedded and recursive.
- **Roles and arms are append-only on edit.** Editing in place destroys the
  ability to trace a turn back to the prompt that produced it. See defect D1.

## Source PDFs

Gitignored (`*.pdf`) — ACM copyright, and the HLD carries client contact
details. Cite by DOI. The three that matter are listed in §7.1 of the plan.

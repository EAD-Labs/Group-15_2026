# Story Studio — Human–AI Co-Creative Storytelling

**ET 617 · Educational Application Development · Group 15**
Tushar Bajaj · Vijaylaxmi Maitri · Anshu Mishra
Client: Florence Lehnert & Marcus Specht, FernUniversität in Hagen

A working prototype of the platform specified in the HLD: an educational
writing environment where the AI **refuses to write the student's story** and
returns Socratic questions instead, while logging every interaction for
research.

---

## Two portals

The app opens on a role chooser (HLD §9.1's Login/Auth screen). It is
prototype sign-in — a name, no password, stored in the browser.

| Portal | Route | What it holds |
|---|---|---|
| **Student** | `/student` | Portfolio, and the split-screen co-creative workspace |
| **Researcher** | `/researcher` | **Study** — conditions, participant assignment, outcome comparison |
| | `/researcher/data` | **Data** — writing-process timeline, both classification axes, sessions, event stream, exports |

Each student gets a `Participant_NN` code that replaces their name in every
export. Students see only their own stories; the researcher sees the whole
cohort. The portal guard is navigation, not security — the API does not
enforce it, and a real deployment would put HLD §7.2's JWT/OAuth2 at that seam.

## Run it

```bash
./run.sh
```

Then open **http://localhost:3000**.

That is the whole setup. The app boots and works with **no API key at all** —
it falls back to a deterministic offline Socratic engine, so the demo can never
fail in front of an audience.

### Live models

A Gemini key is already in `backend/.env` and the app boots on
`gemini-3.5-flash`.

**Free-tier quotas are small and per-model** — `gemini-3.6-flash` allows 20
requests *per day*. The provider therefore walks a fallback chain
(`GEMINI_FALLBACK_MODELS`) when a model returns 429, and only drops to the
offline scaffold when every model is exhausted. When that happens the AI panel
says so rather than passing degraded output off as normal.

Median turn latency on Gemini is ~5s, above the 4s target in HLD §11.1. Two
LLM calls per turn cause it; the classifier already runs on a lite model to
halve its share. The streaming node pipeline is what makes the wait legible.

### For fully offline local inference

```bash
ollama serve
ollama pull qwen2.5:7b
```

Then switch to **Ollama (local)** in the researcher panel — live, no restart.
That switch *is* use case UC-03.

### Containerised (HLD §14 deployment criterion)

```bash
docker compose up --build
```

This variant runs against PostgreSQL instead of SQLite, demonstrating the
Phase 3 storage path. Nothing changes but `DATABASE_URL`.

---

> **Before demoing, check which condition you are in.** Randomised assignment
> can put you in *Unguarded assistant*, where the guardrail is deliberately off
> and the AI will write your story. The workspace shows an amber banner when
> that is the case. To demo the intervention, open
> `/researcher` → Participants and set yourself to *Socratic guardrail*.
> Unassigned students already land in the guarded condition by default.

## A five-minute demo script

1. **Dashboard** → *Start a new story* → pick **Educational Narrative**, click
   the Martian starter, *Open workspace*.
2. In the AI panel, type **"Write the next paragraph for me."**
   Watch the graph nodes light up in sequence, then the amber **REDIRECTED**
   card appear. The request is labelled `executive help`. The AI declines and
   asks a question instead. *This is the whole thesis of the project in one
   interaction.*
3. Click one of the **questions to sit with**, or ask
   **"How can I raise the stakes here?"** — labelled `instrumental help`, and
   allowed straight through. The distinction is Helsinki help-seeking theory.
   Note the second chip on every turn (`planning` / `translating` /
   `reviewing`) — that is the Flower & Hayes axis described below.
3b. **Select a sentence in the editor**, then ask about it. The request is
   scoped to that passage. Open **ways to ask** for the templated prompts.
4. Write a sentence or two in the left pane. Watch the **agency ring** in the
   header stay at 100% — nothing you wrote came from the AI.
5. Expand **▸ trace** under any AI reply to show the five graph nodes that
   produced it.
5b. Open the **scaffold control** in the header: switch to *Light touch* and
   ask again — one probe instead of three, far terser. Switch the model to
   **Ollama (local)** and ask once more; it still refuses to write.
6. Switch portal (top right) → enter as a **researcher** →
   - flip the **model gateway** to another provider (live, no restart) — UC-03
   - edit the **Socratic scaffold** prompt — UC-05
   - set guardrail strictness to **Off** and re-ask "write the next paragraph"
     in the workspace: it now complies. That is the experimental control
     condition, and it proves the guardrail is doing the work.
   - **Study** shows two conditions. Hit **Randomise unassigned**, then read
     *Results* — intercept rate and AI retention separate the arms. That table
     is the "change X → students do Y" answer. Any condition can be edited
     inline; there is no separate global config.
   - **Data** has the writing-process timeline, both classification axes,
     per-session agency/retention, and **export.json / export.csv** — UC-04

---

## How the HLD maps to the code

| HLD section | Where it lives |
|---|---|
| 6.1 M1 — Story Workspace & UI | `frontend/app/story/[id]/page.tsx` |
| 6.1 M2 — Socratic Guardrail & Helsinki engine | `backend/app/graph/nodes.py`, `backend/app/prompts.py` |
| 6.1 M2(iii) — Agency Enforcer | `agency_enforcer()` in `backend/app/graph/nodes.py` |
| 6.1 M3 — Dynamic Model Gateway | `backend/app/providers/` |
| 6.1 M4 — Telemetry & Analytics | `backend/app/routers/research.py`, `backend/app/metrics.py` |
| 7.1 — Agentic state machine, 4 nodes | `backend/app/graph/runner.py` (`GRAPH_SPEC`) |
| 8.2 — Data entities | `backend/app/models.py` (1:1 with the table in the HLD) |
| 9.1 — Screen inventory | `app/page.tsx`, `app/story/[id]`, `app/research` |
| 9.3 — Workspace wireframe | the split-screen layout, incl. the agency % in the header |
| 10.2 — Human Agency Retention eval | `backend/app/metrics.py` (`agency_report`) |
| 9.1 — Login / Auth screen | `frontend/app/page.tsx` (portal chooser) |
| 6.1 M3 — hot-swappable prompts & params | `app/routers/experiments.py` (conditions) |
| 9.1 — Researcher Control Panel + Analytics Hub | `app/researcher` (Study) and `app/researcher/data` (Data) |
| 11.4 — Telemetry anonymisation | `_anonymise()` → `Participant_NN` on every export |

### The five graph nodes

```
intent_classifier → guardrail_verifier → socratic_engine → response_formatter → agency_enforcer
     Node 1               Node 2              Node 3            Node 4          Module 2(iii)
```

Each turn streams its progress over SSE, so the interface can show the filter
firing *before* the answer lands. The path taken is stored on every turn and is
visible in the UI under **trace**.

### The agency metric

`agency_ratio = 1 − (draft 5-grams also present in AI output) / (draft 5-grams)`

Raw counts and a Levenshtein distance to the nearest AI turn ship alongside the
ratio in every export, so a researcher can reconstruct the number rather than
trust it.

---

## Student controls

The student can change **how much scaffolding they get**, and — where the
condition allows — **which model answers**. What they cannot change is whether
the guardrail applies. That distinction is deliberate: the refusal is the
pedagogy, not a preference.

| Level | What changes |
|---|---|
| **Light touch** | One sentence, one probe, under 35 words. For staying in flow. |
| **Balanced** | An observation plus three angles. The default. |
| **Deep dive** | A fuller diagnostic naming what the draft promises but has not paid off. Up to 140 words. |

All three still refuse to write. Intensity is recorded on every turn, so a
researcher can treat it either as a controlled variable (locked per condition)
or as a covariate (student-chosen and logged).

`app/prompts.py` → `SCAFFOLD_INTENSITY` · `components/ScaffoldControl.tsx`

---

## Experiment framework

The research question is "if we change X, do students do Y?" — so conditions
are first-class objects rather than a config file someone edited last Tuesday.

**Conditions** (`/researcher`) bundle every manipulable variable:
provider, model, temperature, guardrail strictness, scaffold intensity, custom
system prompt, and which controls the student is allowed to touch. Two ship by
default: *Socratic guardrail* and *Unguarded assistant* (the control).

**Assignment** is manual per participant, or randomised round-robin over a
shuffled pool — balanced group sizes, random membership, with an optional seed
so an assignment is reproducible.

**Outcomes** are computed per condition on identical definitions, with deltas
against whichever arm is marked control:

| Measure | Reads |
|---|---|
| Human agency | share of the draft not lexically traceable to AI output |
| AI retention | ROUGE-L recall of AI output inside the draft (paper Fig. 7) |
| Intercept rate | share of instructions the Helsinki filter caught |
| Words per exchange | draft words per student instruction |
| Mean draft length | how much got written |
| Median latency | responsiveness under that provider |

Plus both classification axes and which intensities were actually used. Figures
from fewer than three exchanges are dimmed rather than presented as findings.

Every workspace and every turn stores the condition it was produced under, so
re-assigning a participant never rewrites the history of work they already did.

---

## What came from the reference paper

> Chakrabarty, Padmakumar, Brahman & Muresan. **Creativity Support in the Age of
> Large Language Models: An Empirical Study Involving Professional Writers.**
> C&C '24. <https://doi.org/10.1145/3635636.3656201>

An interface study: 17 MFA writers co-wrote 30 stories with GPT-3.5, grounded in
the **cognitive process theory of writing** (Flower & Hayes). Five things from it
are implemented here.

### 1. The cognitive-process axis — every turn is labelled twice

The paper's spine is Flower & Hayes' three non-linear activities: **planning**
(goals and ideas), **translation** (getting thoughts into sentences),
**reviewing** (judging and revising what exists). Their headline result is that
writers seek help across all three but find LLMs most useful for translation and
reviewing, least for planning.

That axis is orthogonal to our Helsinki executive/instrumental axis, so we run
both — in a **single classifier call returning two labels**, so the second axis
costs no extra latency. Every turn now carries e.g. `executive · translating` or
`instrumental · reviewing`, visible as two chips in the workspace, charted
separately in the researcher portal, and present in every export.

This is the substantive addition. It lets the client ask a question the paper
could not: *does a Socratic guardrail shift where students seek help?*

`app/prompts.py` · `app/graph/nodes.py` · `components/CognitiveChart.tsx`

### 2. Templated prompts — kept, but four of five inverted

Section 6.1 reports that "nearly all participants talked about the usefulness of
the templated prompts", so the affordance is worth having. But four of the
paper's five templates (Table 2) are **executive help-seeking** — they ask the
model to produce or rewrite prose, which is exactly what our guardrail exists to
refuse. Each is inverted into the instrumental question serving the same need:

| Paper's template | Ours | Activity |
|---|---|---|
| Generate Continuation | Find what happens next | planning |
| Elaborate Selection | Where is this thin? | reviewing |
| Rewrite with Imagery | Interrogate my imagery | translation |
| Insert Dialogue/Monologue | Test the dialogue | translation |
| Get Feedback | **Critique this** — unchanged | reviewing |

*Get Feedback* survives untouched: it was already instrumental, and it was the
one template writers praised most consistently. Hovering any chip names its
origin. `app/prompts.py` → `TEMPLATES`

### 3. Selection-scoped requests

The paper had writers demarcate a span with `<` and `>` delimiters so an
instruction applied locally rather than to the whole draft (§3.2). A real editor
can just read the selection: highlight any passage and the ask is scoped to it,
shown in a banner above the composer. Their §6.2 records participants asking for
exactly this — "feedback on a particular section of their story instead of
global draft-level feedback".

### 4. The writing-process timeline — a direct reproduction of Figure 6

The paper plots instruction type against instruction index to show writers
alternate between the three activities **non-linearly**, never in tidy phases.
`/researcher/telemetry` renders the same plot from live data, per session or
across the cohort, with intercepted turns ringed. `components/CognitiveTimeline.tsx`

### 5. ROUGE-L retention alongside our agency metric

Figure 7 measures model contribution as the fraction of model-written text
recoverable from the final story, via **ROUGE-L recall** — they found writers
retained under 35% of the model's draft in half the stories. We report the same
statistic next to our own agency ratio, so our numbers are comparable to a
published baseline rather than only to themselves. `app/metrics.py`

### Also: Table 8 as prompt constraints

The paper's taxonomy of *why writers found the AI useless* — repetitiveness,
clichés and tropes, lack of nuance/subtext, and overly moralistic predictable
endings — is written into the system prompt as four named failure modes.

---

## Deliberate deviations from the HLD

These were scoped decisions for an MVP, not oversights.

| HLD says | Prototype does | Why |
|---|---|---|
| LangGraph / LangChain | Five explicit async node functions with a declared `GRAPH_SPEC` | Same topology and state object, no heavy dependency tree, and the path each turn takes can be recorded and drawn in the UI. Swapping in a real `StateGraph` is mechanical. |
| LiteLLM | ~80-line provider adapter | Only two live backends, both with trivial REST APIs. Same interface shape. |
| PostgreSQL | SQLite locally, PostgreSQL under Docker | Keeps local setup to one command. One env var apart. |
| JWT / OAuth2 auth | A single seeded student user | Real auth adds nothing to the pedagogical demo. The `User` entity and role field are in place for it. |
| Dominic's orchestration UI (§7.1, §8.1, §10.1) | Not implemented | Marked "add dominic part" in the source document — his component was out of our scope. |

### Also worth knowing

- **Offline provider is a feature, not a stub.** It composes real Socratic
  moves from the draft and classifies all four help-seeking intents by keyword,
  so every interaction-design claim stays demonstrable with no network.
- **The AI has no "insert into story" button anywhere.** That absence is the
  design position: the only path from a suggestion into the text is the student
  typing it.
- **Nothing is deployed.** Localhost only, per the brief.
- **A 3B local model genuinely tries to write the story.** `_looks_like_narrative()`
  in `app/graph/nodes.py` catches it: a reply that asks nothing *and* narrates
  in past tense using the student's own character names is a continuation, not
  scaffolding. Bigger models rarely trip it; small ones do, which is exactly
  why the enforcer is a separate node rather than a line in the prompt.
- **`compress: false` in `next.config.ts` is deliberate.** Gzip buffers the SSE
  stream until it closes, which kills the live node pipeline. Compression buys
  nothing on localhost.

---

## Layout

```
backend/
  app/
    graph/       state, the five nodes, the runner
    providers/   gemini · ollama · offline scaffold
    routers/     workspaces · chat (SSE) · research
    prompts.py   Helsinki + Flower & Hayes prompts, templates, starters
    metrics.py   agency, Levenshtein, ROUGE-L retention
    models.py    HLD §8.2 entities
    deps.py      portal identity resolution
frontend/
  app/
    page.tsx              portal chooser
    student/              portfolio + story/[id] workspace
    researcher/           study (conditions · participants · results) + data/
  components/    AgencyMeter · NodePipeline · Chat · TemplateRail · ScaffoldControl
                 ConditionCard · OutcomeTable
                 IntentChart · CognitiveChart · CognitiveTimeline
                 PortalGuard · PortalHeader · ExportDialog
  lib/           api client (incl. SSE reader) · session · types
```

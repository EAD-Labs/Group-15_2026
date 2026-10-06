# Story Studio — Human–AI Co-Creative Storytelling

**ET 617 · Educational Application Development · Group 15**
Tushar Bajaj · Vijaylaxmi Maitri · Anshu Mishra
Client: Florence Lehnert & Marcus Specht, FernUniversität in Hagen

A working prototype of the platform specified in the HLD: an educational
writing environment where the AI **refuses to write the student's story** and
asks Socratic questions instead, while logging every interaction for research.

- **Iteration 2** made the Socratic behaviour a configurable, versioned **AI
  role** that behaves differently when the writer is Planning, Translating or
  Reviewing.
- **Iteration 3** lets the system — not the student — decide which of those the
  writer is in (an LLM-based Monitor), and reduces the student side to two
  panels: the story and the chat.

**New here? Read [`docs/how-it-works.md`](docs/how-it-works.md)** — the whole
pipeline, guardrails and AI roles in plain language, with diagrams.

---

## Quick start

### 1. Install the prerequisites (once)

| Tool | Why | How to get it |
|---|---|---|
| **Git** | to download the project | <https://git-scm.com/downloads> |
| **Node.js 20 or newer** | runs the web interface | <https://nodejs.org> (the "LTS" download) |
| **uv** | sets up Python and the backend's packages — it downloads the right Python version itself | macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh`<br>Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

Check they work: `git --version`, `node --version` (should print v20 or
higher) and `uv --version`.

### 2. Download the project

```bash
git clone https://github.com/EAD-Labs/Group-15_2026.git
cd Group-15_2026
```

### 3. Add your Gemini API key

The app works without a key (see *Running without a key* below), but the real
AI tutor needs one. A free key takes about a minute.

1. Go to **<https://aistudio.google.com/apikey>**, sign in with a Google
   account, and click **Create API key**. Copy the key — it is a long string
   that starts with `AIza`.
2. In the project folder, make your own settings file by copying the template:

   ```bash
   cp backend/.env.example backend/.env
   ```

   (On Windows: `copy backend\.env.example backend\.env`)
3. Open **`backend/.env`** in any text editor and find this line:

   ```
   GEMINI_API_KEY=
   ```

   Paste your key straight after the `=`, so it looks like:

   ```
   GEMINI_API_KEY=AIzaSyYourKeyGoesHere
   ```

   **No quotes, no spaces** around the `=`. Save the file. Leave the other
   lines as they are.

> `backend/.env` is ignored by Git, so your key is never uploaded. Never paste
> your key into `backend/.env.example` — that file *is* shared.

### 4. Start the app

**macOS / Linux:**

```bash
./run.sh
```

The first run takes a few minutes (it installs everything); later runs start in
seconds. When you see **"Story Studio is running"**, open
**<http://localhost:3000>**. Press **Ctrl + C** in the terminal to stop.

**Windows** (in two separate terminals, from the project folder):

```powershell
# terminal 1 - backend
cd backend
uv venv --python 3.13
uv pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx python-multipart
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# terminal 2 - frontend
cd frontend
npm install
npm run dev
```

Then open **<http://localhost:3000>**.

### 5. Check the AI is live

Open **<http://localhost:8000/api/health>**. You should see
`"provider_healthy": true` and `"Ready (gemini-3.5-flash)"`. If it says
`"No API key set"`, see *Troubleshooting* below.

### Changed the key later?

The key is read when the backend starts. After editing `backend/.env`, **stop
the app (Ctrl + C) and start it again.**

---

## Troubleshooting

| What you see | Why | Fix |
|---|---|---|
| Replies look generic and repeat (e.g. *"Before the prose, there's a decision here you haven't committed to…"*) | The AI is running on the built-in offline tutor, not Gemini | 1) Check the key is in `backend/.env` exactly as in step 3 and restart. 2) Check each study condition uses Gemini: sign in as **Researcher → Study → edit** on each condition → **model: Google Gemini**. (Databases created by older versions could have saved the conditions as "Offline Scaffold".) |
| `/api/health` says `"No API key set"` | The key isn't being read | The file must be named exactly `backend/.env` (not `.env.txt` — Windows Notepad adds `.txt`; choose "All files" when saving), the line must be `GEMINI_API_KEY=...` with no quotes, and the backend must be restarted |
| Works for a while, then replies turn generic | The free Gemini tier has small **daily** limits per model | The app automatically tries other Gemini models first (`GEMINI_FALLBACK_MODELS`), then the offline tutor. Wait for the quota to reset (daily), or use a paid key |
| `./run.sh: permission denied` | The script isn't marked executable | `chmod +x run.sh` then `./run.sh` again |
| `uv: command not found` | uv isn't installed, or the terminal was opened before installing | Install it (step 1), then open a **new** terminal |
| `Port 3000/8000 is already in use` | An earlier copy is still running | Close the other terminal, or on macOS/Linux: `lsof -ti :3000 -ti :8000 \| xargs kill` |

### Running without a key

Everything still works: each turn falls back to a deterministic offline
Socratic tutor, and the writing-activity Monitor falls back to a transparent
rule. Useful for a demo with no internet, but replies are much less specific.

### For fully offline local inference

```bash
ollama serve
ollama pull qwen2.5:3b
```

Then point a condition at **Ollama (local)** in the researcher portal — live, no
restart. That switch *is* use case UC-03.

### Containerised (HLD §14 deployment criterion)

For Docker, the key goes in a **`.env` file in the project root** (next to
`docker-compose.yml`), not in `backend/.env`:

```
GEMINI_API_KEY=AIzaSyYourKeyGoesHere
```

```bash
docker compose up --build
```

This variant runs against PostgreSQL instead of SQLite, demonstrating the
Phase 3 storage path. Nothing changes but `DATABASE_URL`.

### Hosting it

Nothing is deployed by default — localhost only, per the brief — but both
services are already Dockerised, so putting this on the internet is a hosting
step, not a rebuild. The one thing to design around: the turn endpoint streams
its reply over SSE, so pick a host that runs your container as a normal,
long-lived process. Pure serverless/edge platforms can cut that stream short.

**Free path:** [Render](https://render.com) for both services (`render.yaml`
at the repo root — Render → New → Blueprint → point it at this repo) +
[Neon](https://neon.tech) for Postgres. Not Render's own free Postgres — it
auto-deletes after 90 days, which is a silent data-loss trap for a
semester-long study. Neon's free tier doesn't expire.

What to set:
- Backend: `DATABASE_URL` (Neon's connection string, with the
  `postgresql+psycopg://` prefix), `GEMINI_API_KEY`.
- Frontend: `BACKEND_URL` → the backend service's public Render URL.
- Backend `ALLOWED_ORIGINS` → the frontend's public URL, as a second layer of
  defence (the browser normally only ever talks to the frontend; this only
  matters if something calls the backend directly, e.g. its `/docs` page).

Free-tier web services sleep after 15 minutes idle; the next request wakes
them with a ~30–50s delay, but won't cut off a reply already streaming.

---

## Two portals

The app opens on a role chooser (HLD §9.1's Login/Auth screen). It is
prototype sign-in — a name, no password, stored in the browser.

| Portal | Route | What it holds |
|---|---|---|
| **Student** | `/student` | Their stories, and the two-panel workspace: story + writing partner |
| **Researcher** | `/researcher` | **Study** — conditions, AI roles, participant assignment, outcome comparison |
| | `/researcher/data` | **Data** — writing-process timeline (incl. the Monitor's decisions and reasons), classification charts, sessions, event stream, exports |

Each student gets a `Participant_NN` code that replaces their name in every
export. Students see only their own stories; the researcher sees the whole
cohort. The portal guard is navigation, not security — the API does not
enforce it, and a real deployment would put HLD §7.2's JWT/OAuth2 at that seam.

> **Before a session, check which condition each student is in.** Randomised
> assignment can put a student in *Unguarded assistant*, where the guardrail
> is deliberately off and the AI will write their story. The student is **not**
> told (that would bias the study) — check in **Researcher → Study →
> Participants**. Unassigned students land in *Socratic guardrail* by default.

**Performance.** A turn takes around 5 seconds on Gemini's free tier. Three
LLM calls are involved — the help-seeking classifier and the Monitor run in
parallel on a lite model, then the tutor replies — and the student sees plain
status lines ("Reading your question…", "Thinking it through…") meanwhile.

---

## A five-minute demo script

1. Enter as a **student** → *New story*. The form asks for three things only:
   a title, an optional brief idea (anything — a plot sketch, a journal entry),
   and the first line.
2. The workspace is two panels: the story, and the chat. Nothing else.
3. Ask **"What should happen next in the plot?"** The Monitor decides this is
   *planning* (a planning-shaped message on a near-empty page) and the tutor
   opens options rather than closing them.
4. Write a paragraph, then send just **"thanks"**. The message itself says
   nothing about activity, but the draft grew since the last ask — the Monitor
   decides *translating*, and the tutor talks about the sentences.
5. Ask **"Give me a critique of this passage."** → *reviewing*.
6. Ask **"Write the next paragraph for me."** The tutor declines in one line and
   gives a question instead — still the whole thesis of the project.
7. Switch portal → **researcher** → **Data**. The writing-process timeline has
   the classifier's detected activity (filled dots) and the Monitor's decision
   (hollow squares) per turn; on the "thanks" turn they disagree, which is the
   point. `export.json` carries every decision with its evidence.
8. **Study** still holds conditions, AI roles (edit the Tutor's per-activity
   prompts — append-only versions), participants and the outcome comparison.

---

## How the HLD maps to the code

| HLD section | Where it lives |
|---|---|
| 6.1 M1 — Story Workspace & UI | `frontend/app/student/story/[id]/page.tsx` |
| 6.1 M2 — Socratic Guardrail & Helsinki engine | `backend/app/graph/nodes.py`, `backend/app/prompts.py` |
| 6.1 M2(iii) — Agency Enforcer | `agency_enforcer()` in `backend/app/graph/nodes.py` |
| 6.1 M3 — Dynamic Model Gateway | `backend/app/providers/` |
| 6.1 M4 — Telemetry & Analytics | `backend/app/routers/research.py`, `backend/app/metrics.py` |
| 7.1 — Agentic state machine, 4 nodes | `backend/app/graph/runner.py` (`GRAPH_SPEC`) |
| 8.2 — Data entities | `backend/app/models.py` (1:1 with the table in the HLD) |
| 9.1 — Screen inventory | `app/page.tsx`, `app/student/story/[id]`, `app/researcher` |
| 9.3 — Workspace wireframe | the split-screen layout, incl. the agency % in the header |
| 10.2 — Human Agency Retention eval | `backend/app/metrics.py` (`agency_report`) |
| 9.1 — Login / Auth screen | `frontend/app/page.tsx` (portal chooser) |
| 6.1 M3 — hot-swappable prompts & params | `app/routers/experiments.py` (conditions) |
| 9.1 — Researcher Control Panel + Analytics Hub | `app/researcher` (Study) and `app/researcher/data` (Data) |
| 11.4 — Telemetry anonymisation | `_anonymise()` → `Participant_NN` on every export |
| Iteration 2 — configurable AI roles | `AIRole` in `backend/app/models.py`; `/api/research/roles`; `components/RoleCard.tsx` |
| Iteration 2 — activity-conditioned behaviour | `build_system_prompt()` in `backend/app/prompts.py` |
| Iteration 3 — system-decided activity (Monitor) | `backend/app/graph/monitor.py`; `activity_monitor()` in `backend/app/graph/nodes.py` |

### The six graph nodes

```
intent_classifier → activity_monitor → role_arbiter → response_engine → response_formatter → agency_enforcer
     Node 1          F&H's Monitor        Node 2           Node 3            Node 4          Module 2(iii)
```

`activity_monitor` was added in iteration 3 — see **Iteration 3** below.

Renamed in iteration 2 (`guardrail_verifier` → `role_arbiter`, `socratic_engine`
→ `response_engine`) because a node named after one behaviour can't host four —
see **Iteration 2** below. Each turn streams its progress over SSE, so the
interface can show the filter firing *before* the answer lands. The path taken
is stored on every turn and is visible in the UI under **trace**.

### The agency metric

`agency_ratio = 1 − (draft 5-grams also present in AI output) / (draft 5-grams)`

Raw counts and a Levenshtein distance to the nearest AI turn ship alongside the
ratio in every export, so a researcher can reconstruct the number rather than
trust it.

---

## Student controls

None. Since iteration 3 the student sees their story and the chat, and has no
control over the model, the scaffold intensity or the writing activity. Scaffold
intensity (`light | balanced | deep`, `app/prompts.py` → `SCAFFOLD_INTENSITY`)
is set per condition by the researcher and recorded on every turn. The
`allow_student_*` fields still exist on conditions for old data but nothing in
the student UI reads them.

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

## Iteration 3 — the system decides the writing activity; a minimal student UI

Driven by the professor's feedback after iteration 2:

1. **The writing activity is decided by an algorithm**, not chosen by the
   student and not set by the researcher. Iteration 2's *"what are you doing
   right now?"* toggle is gone.
2. **The student side is two panels** — story and chat — with a dashboard that
   lists stories and a three-field new-story form (title, optional brief idea,
   first line). No model picker, scaffold control, agency meter, templates,
   export, classification chips or graph trace. All of that is still computed
   and stored; it is read on the researcher side.
3. The Next.js dev badge ("N", bottom left) is hidden (`devIndicators: false`).

### The Monitor (`backend/app/graph/monitor.py`)

Flower & Hayes' fourth component is the **Monitor** — *"a writing strategist
which determines when the writer moves from one process to another."* Iteration
3 implements it as a new graph node that runs before the prompt is built.

**An LLM decides.** The Monitor gives Gemini (`GEMINI_MONITOR_MODEL`, default
the lite model) a brief on Flower & Hayes' three processes — explicitly *not*
sequential — plus the whole situation: the student's message, any selected
passage, the draft and how it changed since the last question, the recent
exchange with the tutor, the student's notes, and its own previous judgement.
It returns the process, a confidence and a one-line reason
(`prompts.MONITOR_SYSTEM_PROMPT`, versioned as `MONITOR_PROMPT_VERSION`).
Context is the point: *"thanks"* or *"ok yes"* mean nothing alone, but after
the tutor asked about a specific phrase, "ok yes" is reviewing.

The call starts in parallel with the intent classifier, so it adds no latency
to the turn in practice.

**A transparent rule is the fallback and the baseline.** When no LLM is
reachable (offline scaffold, exhausted quota, unparseable reply) the rule below
decides, so the demo never breaks. It is also computed on *every* turn and
stored beside the LLM's call, so the researcher can see how often the LLM's
contextual judgement departs from surface signals (`agrees_with_rules`, and an
agreement rate on the Data page).

| Signal | Points to | Weight | Grounding |
|---|---|---|---|
| Classifier's label for the message | that activity | 3.0 | C&C '24 labels activity from the instruction itself |
| Draft under 30 words | planning | 1.5 | F&H: goals and ideas precede prose |
| Draft grew ≥ 25 words since last ask | translating | 1.0 | text being produced = translating |
| Draft shrank ≥ 5 words since last ask | reviewing | 1.0 | revision deletes |
| Asking about a selected passage | reviewing / translating | 1.0 / 0.5 | C&C '24 §3.2 selection-scoped instructions act on existing text |
| Brainstorm intent | planning | 0.75 | F&H's *generating* sub-process |
| Previous turn's decision | same activity | 0.75 | inertia — an aside shouldn't reset the phase |

Either way there is **no transition ordering** — any activity can follow any
other (F&H: processes embed and recurse).

Every turn stores `decided_activity` plus `activity_evidence` — `method`
(`llm` | `rules`), and for the LLM its reason, confidence, model and prompt
version; plus the rule's full verdict (score per activity, each contributing
signal) — and `draft_words`. Changing the prompt means bumping
`MONITOR_PROMPT_VERSION`; changing the weights, `MONITOR_VERSION`. Turns stay
traceable to what decided them — the same append-only logic as roles (D1).
Export schema is now **1.2**.

The student's optional brief idea is stored as `StoryWorkspace.notes` and given
to the tutor as context.

Existing databases gain the new columns automatically at boot
(`ensure_columns()` in `backend/app/db.py`, additive only).

---

## Iteration 2 — configurable AI roles & activity-conditioned behaviour

Driven by Florence's email after the first demo: keep the Socratic Tutor as the
one implemented role, but stop hard-coding it, so researchers can configure or
replace it later without touching the core application; and make the Tutor
behave differently across Planning, Translating and Reviewing rather than
detecting the activity and never acting on it. Full rationale, literature
grounding and phase-by-phase plan: `docs/iteration-2-plan.md`.

### AI roles are now data, not code

`AIRole` (`backend/app/models.py`) replaces the old `guardrail_strictness`
integer with a named, versioned record: archetype (`ghost | partner | tutor |
custom`, Steinhoff & Lehnen's GPT model), behaviour, a base prompt, one prompt
fragment per writing activity, `may_produce_prose`, and an `enforcement_level`.
Two roles ship by default — **Socratic Tutor** and **Ghost baseline** — mapped
onto the two existing conditions with byte-identical behaviour to before.

**Edits are append-only.** `PATCH /api/research/roles/{id}` writes a *new
version* and repoints every condition using the old one; the old row is never
mutated, so a turn tagged with `role_version_id` can always be traced back to
the exact prompt text that produced it. Manage roles from `/researcher` → **AI
roles** (`components/RoleCard.tsx`); a condition now picks a role instead of a
strictness level (`components/ConditionCard.tsx`).

Role and enforcement are also split apart: a Ghost writing prose is the role
working *correctly*, not a guardrail failure, so `agency_enforcer` now always
runs and always logs — including for the Ghost, which previously produced no
enforcement telemetry at all.

### The Tutor behaves differently per writing activity

`build_system_prompt()` appends the role's fragment for the *effective*
activity — in iteration 2 the writer's own declaration if they made one, else
whatever the classifier detected; since iteration 3, the Monitor's decision. `AIRole.{planning,translating,reviewing}_prompt` hold
placeholder heuristics (`backend/app/prompts.py` →
`TUTOR_PLANNING_FRAGMENT` etc.) pending Florence's own; because roles are now
data, swapping hers in needs no redeploy.

> **Superseded in iteration 3:** the toggle below was removed; the system's
> Monitor now decides the activity. Kept here as the record of iteration 2.

**The writer's Monitor.** A new control in the workspace —
*"what are you doing right now?"* (`components/ActivityControl.tsx`) — lets the
writer declare Planning / Translating / Reviewing. Deliberately **not a
stepper**: three equal toggles, no ordering, no completion state, and clicking
the active one clears it, per Flower & Hayes' insistence that these activities
are embedded and recursive rather than sequential. Declared and detected
activity are both stored on every turn, both exported, and a mismatch between
them is shown to the student as a small, non-nagging note — and to the
researcher as a second track on the writing-process timeline
(`components/CognitiveTimeline.tsx`).

### Measurement fixes for a real user test

- **Participant attribution** — `POST /api/research/events` used to file every
  event under the first student in the table; it now resolves the actual caller
  from `X-User-Id`, falling back to the workspace owner.
- **A fourth activity label, `other`** — the classifier was forced into
  `planning | translation | reviewing` and defaulted unmatched turns to
  `planning`, inflating that bucket. It now has the fourth `other` bucket the
  reference paper's own annotators used.
- **Retention by activity** — `/api/research/experiments/compare` and
  `/api/research/summary` report AI-retention broken down by writing activity
  (`OutcomeTable.tsx`'s *AI retention by writing activity* panel), surfacing
  where footnote 18 of the reference paper — Reviewing text isn't meant to
  enter the draft — would change the headline number.
- **Writer goals** — a short, optional per-story goal field
  (`StoryWorkspace.goals`), shown above the editor, that the Tutor is told
  about so it can hold the draft against the writer's own aim rather than only
  generic craft advice.
- Assorted housekeeping: the dead `/research` link removed from the student
  header, stale routes/paths corrected in this README and `run.sh`, and the
  Gemini model default aligned between `backend/app/config.py` and
  `docker-compose.yml`.

### Tests

`backend/tests/` (35 tests, incl. `test_iteration3_monitor.py`). Install pytest
once, then run them:

```bash
cd backend
uv pip install pytest
.venv/bin/python -m pytest -q
```

Covers, among other things: the Tutor's composed system prompt is
byte-identical to the pre-role-system version; editing a role creates a new
version and repoints conditions without touching the old row; the same
question under declared Planning vs Reviewing produces materially different
replies; and telemetry events are attributed to the right participant when two
people write at once.

### Status

Iteration 2 is merged into `main`; iteration 3 is on branch `iteration-3`.
`AIRole`, activity-conditioned prompts and the Monitor control are Phase 1 +
Phase 2 of the plan; the measurement fixes above are Phase 3, partially done —
see `docs/iteration-2-plan.md` §9 for what's still open (chiefly: append-only
edits for *conditions*, not just roles, and excluding Reviewing turns from the
headline retention figure, both pending a decision from the client).

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
`/researcher/data` renders the same plot from live data, per session or
across the cohort, with intercepted turns ringed, and (iteration 2) a second
track for the writer's declared activity. `components/CognitiveTimeline.tsx`

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
  stream until it closes, which kills the live status lines. Compression buys
  nothing on localhost.

---

## Layout

```
backend/
  app/
    graph/       state, the six nodes, the runner, monitor.py (activity decision)
    providers/   gemini · ollama · offline scaffold
    routers/     workspaces · chat (SSE) · research (incl. /roles) · experiments
    prompts.py   Helsinki + Flower & Hayes prompts, templates, starters,
                 per-activity role fragments
    metrics.py   agency, Levenshtein, ROUGE-L retention
    models.py    HLD §8.2 entities + AIRole (iteration 2)
    deps.py      portal identity resolution
  tests/         pytest, 35 tests
frontend/
  app/
    page.tsx              portal chooser
    student/              portfolio + story/[id] workspace
    researcher/           study (conditions · roles · participants · results) + data/
  components/    AgencyMeter · Chat · ConditionCard · RoleCard · OutcomeTable
                 IntentChart · CognitiveChart · CognitiveTimeline
                 PortalGuard · PortalHeader
  lib/           api client (incl. SSE reader) · session · types
docs/
  iteration-2-plan.md   the client's iteration-2 ask, phased plan, open questions
```

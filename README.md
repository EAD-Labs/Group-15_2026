# Story Studio — Human–AI Co-Creative Storytelling

> **[→ Project introduction page](https://ead-labs.github.io/Group-15_2026/)** — what Story Studio is and a short walkthrough, for non-technical readers.

**ET 617 · Educational Application Development · Group 15**
Tushar Bajaj · Vijaylaxmi Maitri · Anshu Mishra
Client: Florence Lehnert & Marcus Specht, FernUniversität in Hagen

---

## What it is

Story Studio is a writing environment for university students. The student
writes their own story, and an AI writing partner beside it helps them plan,
draft and revise. **The partner never writes the story for them.**

**Why:** AI can write a whole story in seconds, and a student who lets it skips
the thinking that writing is meant to teach. Story Studio keeps the AI useful
while leaving the writing to the student. It also records every interaction,
anonymised, so researchers can study how students write with AI.

**Who it's for:** students writing short stories, and the teachers and
researchers studying AI-assisted writing.

## What it does

- **Two panels for the student**: their story on the left, the writing partner
  on the right. No AI settings and no scores on the student's screen.
- **A partner that helps without taking over.** It answers spelling or grammar
  questions directly, offers a few options when the direction is open, and when
  asked to write, says the words should be the student's and helps them work
  out what the passage needs.
- **It adapts to what the writer is doing.** The system works out whether the
  student is planning, drafting or revising, and the partner responds
  accordingly.
- **A researcher portal** to set up study conditions (for example, this partner
  vs. an ordinary AI assistant as a control), edit the AI's instructions
  without touching code, compare groups, and export anonymised data.

## Run it

**1. Install once:** [Git](https://git-scm.com/downloads),
[Node.js 20+](https://nodejs.org) and [uv](https://docs.astral.sh/uv/)
(macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`;
Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`).

**2. Download:**

```bash
git clone https://github.com/EAD-Labs/Group-15_2026.git
cd Group-15_2026
```

**3. Add a Gemini API key** (free, about a minute; optional, see below):
get one at <https://aistudio.google.com/apikey>, then

```bash
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
```

and paste the key into `backend/.env` after `GEMINI_API_KEY=` (no quotes, no
spaces). The file is git-ignored, so the key is never uploaded.

**4. Start (macOS / Linux):**

```bash
./run.sh
```

The first run installs everything and takes a few minutes. When it prints
**"Story Studio is running"**, open **<http://localhost:3000>**. Ctrl + C stops it.

**Windows**, in two terminals from the project folder:

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

**5. Check the AI is live:** <http://localhost:8000/api/health> should show
`"default_provider": "gemini"` and `"provider_status": "Ready (gemini-3.5-flash)"`.
If it says `"deterministic offline mode"`, the key isn't being read.

**No key?** The app runs, but the partner answers "unavailable" until a key is
added. To demo without a key or internet, go to **Researcher → Study**, edit a
condition, and set its model to **Offline Scaffold**, or set "on failure" to
**use the offline backup**. The offline partner is much less specific.

Docker, a fully local model (Ollama) and free hosting are covered in
[`docs/technical-notes.md`](docs/technical-notes.md#other-ways-to-run-it).

## Using it

The app opens on a sign-in screen: pick **Student** or **Researcher** and enter
a name (no password; this is a prototype).

| Portal | Where | What's there |
|---|---|---|
| Student | `/student` | Your stories, and the two-panel workspace |
| Researcher | `/researcher` | Study conditions, AI roles, participant assignment, results |
| | `/researcher/data` | Writing-process timeline, charts, sessions, anonymised exports |

> **Before a study session**, check each student's condition under
> **Researcher → Study → Participants**. Random assignment can place a student
> in *Unguarded assistant*, the control condition, where the AI will write for
> them. Unassigned students get the *Socratic guardrail* condition.

## Troubleshooting

| Problem | Fix |
|---|---|
| Partner says it's unavailable | No working Gemini key. Check `backend/.env` (step 3) and restart. |
| Replies are generic and repetitive | A condition is on the offline partner. Under **Researcher → Study**, set each condition's model to **Google Gemini**. |
| `/api/health` says "deterministic offline mode" | The key isn't being read. The file must be named exactly `backend/.env` (not `.env.txt`), the line must read `GEMINI_API_KEY=...`, and the backend must be restarted. |
| Works for a while, then stops replying | The free Gemini tier has daily limits. Wait for the reset, or use a paid key. |
| `./run.sh: permission denied` | `chmod +x run.sh` |
| `uv: command not found` | Install uv (step 1), then open a new terminal. |
| Port 3000 or 8000 already in use | Close the other copy, or `lsof -ti :3000 -ti :8000 \| xargs kill` |

## Tests

```bash
cd backend
uv pip install pytest
.venv/bin/python -m pytest -q        # 93 tests
```

To compare the partner's replies across models: `backend/eval/suite.py`.

## Project layout

```
backend/    FastAPI app: the AI pipeline (app/graph), prompts, model providers, database
frontend/   Next.js app: student workspace and researcher portal
docs/       introduction page, explainers, plans, evaluation results
run.sh      one-command local start
```

## Documentation

| Document | For |
|---|---|
| [`docs/index.html`](docs/index.html) | Source of the introduction page |
| [`docs/how-it-works.md`](docs/how-it-works.md) | The pipeline, guardrails and AI roles in plain language, with diagrams |
| [`docs/technical-notes.md`](docs/technical-notes.md) | HLD-to-code map, iteration history, research grounding, design decisions |
| [`docs/UPDATES.md`](docs/UPDATES.md) | Iteration 4: fixes from the client's heuristic evaluation |
| [`docs/iteration-2-plan.md`](docs/iteration-2-plan.md) | The client's iteration-2 request and how it was planned |
| [`docs/eval/final-2026-10-13.md`](docs/eval/final-2026-10-13.md) | Gemini vs. local model on the client's test questions |

Reference paper: Chakrabarty, Padmakumar, Brahman & Muresan, *Creativity
Support in the Age of Large Language Models*, C&C '24,
<https://doi.org/10.1145/3635636.3656201>.

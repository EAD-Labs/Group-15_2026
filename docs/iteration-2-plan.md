# Iteration 2 — Writing Activities & Configurable AI Roles

**Story Studio · ET 617 Group 15**
Tushar Bajaj · Vijaylaxmi Maitri · Anshu Mishra
Client: Florence Lehnert & Marcus Specht, FernUniversität in Hagen

| | |
|---|---|
| **Written** | 2026-09-08 |
| **Driven by** | Florence's email following the 2026-09-02 demo |
| **Next client meeting** | Wednesday 2026-09-09 |
| **Target** | A working prototype for user testing "over the upcoming weeks" |
| **Status** | Planning — nothing in this document is implemented yet |

---

## 0. How to read this document

Sections 1–5 are the *why*: what the client asked for, what it means, and what
the architecture has to become. Section 6 is the *what*: four phases, each with
concrete file-level changes and acceptance criteria. Sections 7–9 are reference
material — literature citations, open decisions, and pre-existing defects that
this iteration has to absorb.

If you are picking this up cold, read §2, §3, then jump to whichever phase is
current. If you are in the client meeting, §2 and §3 are the slides.

**Nothing here has been built.** Every "should", "becomes" and "gains" is a
proposal. Section 8 tracks which proposals have actually been agreed.

---

## 1. What the client asked for

Florence's email proposes two dimensions for the next iteration, plus a
constraint that matters more than either of them.

**Dimension 1 — Writing process.** Distinguish Planning, Translating and
Reviewing from the cognitive writing-process model. Explicitly: *"These should
not necessarily be sequential steps; writers should be able to move freely
between them."* She cites the C&C '24 paper as the interface example and
Flower & Hayes as the underlying theory.

**Dimension 2 — Configurable AI roles.** Steinhoff & Lehnen's GPT model —
Ghost / Partner / Tutor, paired with the human roles Client / Explorer /
Learner. Keep the Socratic Tutor as the one implemented role for now.

**The constraint, which is the actual deliverable:**

> "…it would be good to keep the underlying architecture flexible so that we and
> other researchers can later configure different AI roles and behaviours,
> rather than having the Socratic behaviour hard-coded into the system."

and

> "researchers should in the future be able to replace the Socratic Tutor with,
> for example, a creative Partner, critical Partner, Ghost/baseline condition,
> or another researcher-defined role **without having to change the core
> application**."

She also says: *"I will provide some more detailed heuristics for this later."*
That single sentence sets a hard requirement — heuristics must be loadable
**without a redeploy**, which means they live in the database and are editable
from the researcher portal, not in `prompts.py`.

Her worked example of what the combination buys:

> "During Planning, it might ask questions that help the writer develop and
> explore ideas; during Translating, it could scaffold how the writer expresses
> an idea without simply writing the text for them; and during Reviewing, it
> could encourage reflection on coherence, assumptions, alternatives, or
> possible revisions."

---

## 2. The framing correction (read before the meeting)

Florence writes that the writing-process dimension *"has not yet been
implemented."* Our instinct is to say it has — we classify every turn as
planning/translating/reviewing, chart both axes, and reproduce the paper's
Figure 6.

**Do not lead with that.** Her reading is closer to right than ours. The precise
distinction, which is the thing to say out loud:

> We **detect** the writing activity. We do not **condition on** it.

The classification is pure instrumentation. It goes into `ConversationTurn.
cognitive_activity`, into the charts, into the export — and never comes back out
into the interaction. Every turn gets the same system prompt regardless of
whether the student is planning or reviewing. Her example above is exactly the
gap.

The same is true of dimension 2, in a more encouraging way:

> We have already built two AI roles. We just spelled them as an integer.

`guardrail_strictness = 2` is a Tutor. `guardrail_strictness = 0` with
`CONTROL_SYSTEM_PROMPT` — *"Write whatever they ask for: continue their scene,
draft paragraphs, rewrite their sentences"* — is a Ghost in everything but name.
Steinhoff & Lehnen give us the vocabulary we were missing, and the refactor is
mostly renaming things that already exist into terms the client and the
literature share.

**Meeting posture:** agree with her, name the detect-vs-condition distinction,
show the three-dimension model in §3, and bring the open questions in §6 Phase 0.

---

## 3. The conceptual model — three dimensions

Florence's own summary, which we adopt verbatim as the architecture:

| Dimension | Values | Who sets it | Where it lives |
|---|---|---|---|
| **Writing activity** | Planning · Translating · Reviewing (· Other) | detected per turn, and declared by the writer | `ConversationTurn` |
| **AI role** | Ghost · Partner · Tutor · custom | researcher, per condition | `AIRole` → `ExperimentArm` |
| **Behaviour** | Socratic questioning · brainstorming · critical reflection · direct generation · … | researcher, per role | `AIRole` |

Two properties of this model that the code must respect:

**Activities are not stages.** Flower & Hayes are emphatic: *"people do not march
through these processes in a simple 1, 2, 3 order"*, the processes are
hierarchically embedded, and one can recurse inside another. Their Figure 2
shows plan→translate→review→plan→translate→review inside a *single sentence*.
Consequence for the UI: no progress bar, no ordering, no "current phase"
indicator, no completion state. Chips and a timeline are fine; a stepper is not.

**Roles are prototypes, not an enum.** Steinhoff & Lehnen draw their model as
*overlapping Venn circles* and say so explicitly — the roles *"are not sharply
separable but form intersections"*, and the model's value is in **locating** a
phenomenon in the spectrum, "in one circle or between two or three." Their
Costello example has the AI moving between Partner and Tutor inside one
conversation. Consequence: named presets are fine; presenting the role as ground
truth about what happened is not. We configure a role and **measure the drift**.

### The mapping we already had without knowing it

Our existing Helsinki help-seeking axis is close to Steinhoff & Lehnen's *human*
role axis. Worth a slide:

| Our `intent_type` | S&L human role | S&L AI counterpart | S&L chat practice |
|---|---|---|---|
| `executive` | Client | Ghost | Chat-to-Generate |
| `brainstorm` | Explorer | Partner | Chat-to-Create / Chat-to-Chat |
| `instrumental` | Learner | Tutor | Chat-to-Create / Chat-to-Chat |
| `reflection` | *(no clean mapping)* | — | — |

State the imperfection honestly — `reflection` doesn't map, and the circles
overlap by design. But the payoff is real: **we already measure the role the
student is acting out, and the arm configures the role the AI is playing.** The
mismatch between the two is a finding. A student assigned a Tutor who keeps
behaving as a Client is the interesting case, and it is measurable today.

### Where our app sits in the GPT model

Structurally Story Studio is a **Chat-to-Create** environment: the human owns
the artifact, the chat sits beside it, the output of the chat does not
automatically become the text. This is worth naming because it justifies a
design decision we already made — *"the AI has no 'insert into story' button
anywhere"* — and because it creates a problem for the Ghost baseline (§8, Q1).

---

## 4. Where the current code sits

### What already maps well and should be kept

| Asset | Why it survives |
|---|---|
| `ExperimentArm` | Already the right container: bundles every manipulable variable, snapshotted onto workspaces and turns. Gains a `role_id`; loses `guardrail_strictness`. |
| `GRAPH_SPEC` as data | The UI draws whatever is in it, so node renames are nearly free. |
| Two-axis classifier in one call | Second axis costs no extra latency. Keep. |
| `SCAFFOLD_INTENSITY` composition pattern | `base + addendum` is exactly the shape per-activity fragments need. |
| `agency_enforcer` as a separate node | Structural check, not a prompt line. More necessary after this change, not less. |
| Offline `echo` provider | Demo insurance. Must be extended to cover new roles. |

### What blocks the client's ask

| Problem | Location | Consequence |
|---|---|---|
| Role is hard-coded in a Python branch | `prompts.build_system_prompt()` | Adding a role = editing source + redeploy. Directly violates the client's constraint. |
| Role and enforcement are one integer | `guardrail_strictness` | A Ghost gets **no** enforcement at all — `agency_enforcer` returns early at `strictness == 0`, so we lose all enforcement telemetry in the control arm. |
| Behaviour does not vary by activity | `nodes.socratic_engine`, `prompts.py` | This is client request #1. |
| Activity is detected but never used | `TurnState.cognitive` | Written to the DB, never read back into the prompt. |
| Arms are mutated in place | `experiments.update_arm()` | See §9 D1 — becomes fatal once heuristics are editable. |
| Three-way forced activity choice | `_cognitive_fallback()` | Everything unclassifiable is filed as `planning`. See §9 D3. |

---

## 5. Target architecture

### 5.1 New entity: `AIRole`

Stored, versioned, researcher-editable. This is the seam the client asked for.

```
AIRole
  role_id                 str, pk
  name                    "Socratic Tutor" | "Critical Partner" | "Ghost baseline"
  archetype               ghost | partner | tutor | custom      # Steinhoff & Lehnen
  behaviour               socratic_questioning | brainstorming
                          | critical_reflection | direct_generation | custom
  base_prompt             text
  planning_prompt         text   # ← per-activity heuristics
  translating_prompt      text   #   (Florence will supply these)
  reviewing_prompt        text
  may_produce_prose       bool   # replaces strictness == 0
  enforcement_level       int    # 0..2, how strictly we police the contract
  version                 int    # immutable; edits create a new row
  parent_role_id          str    # version chain
  created_at              datetime
```

`ExperimentArm` then loses `guardrail_strictness` and `system_prompt`, and gains
`role_id`. Every `ConversationTurn` gains `role_version_id` so a turn can always
be traced to the exact prompt text that produced it (§9 D1).

### 5.2 Separating role from enforcement

These are two different questions that `guardrail_strictness` currently answers
with one number:

| | Question | Today | Target |
|---|---|---|---|
| **Role** | What is this AI *supposed* to do? | `strictness == 0` → Ghost, else Tutor | `AIRole.archetype` + `may_produce_prose` |
| **Enforcement** | How hard do we police deviation? | same integer | `AIRole.enforcement_level` |

A Ghost writing prose is the role **working correctly**, not a guardrail
failure. It should still be logged, measured, and checked against its own
contract. The enforcer stops meaning "no prose ever" and starts meaning "does
the output match the declared role's contract?"

### 5.3 Node renames (not cosmetic)

```
intent_classifier  →  intent_classifier      (unchanged; gains "other" label)
guardrail_verifier →  role_arbiter
socratic_engine    →  response_engine
response_formatter →  response_formatter     (unchanged)
agency_enforcer    →  agency_enforcer        (contract-relative, not absolute)
```

- **`role_arbiter`** currently does one thing: `intercepted = intent ==
  "executive" and strictness >= 1`. It should resolve *(declared role × detected
  activity × detected human role)* into what this turn is permitted to be.
  Interception becomes one possible outcome of a Tutor, not the pipeline's only
  behaviour.
- **`response_engine`** — a node named after one behaviour cannot host four.

### 5.4 Prompt composition

`build_system_prompt()` gains an `activity` argument and reads from the role
record rather than module constants:

```
role.base_prompt
  + role.<activity>_prompt          ← new: the client's dimension 1
  + intercept_addendum   (if the arbiter intercepted)
  + strictness_addendum  (if enforcement_level >= 2)
  + intensity_addendum   (existing scaffold intensity)
```

Same layering as today. One new layer, and the base now comes from the DB.

---

## 6. Phases

Each phase is independently shippable. Phase 1 deliberately produces **no
visible change** — that is how we know the refactor is clean.

---

### Phase 0 — Settle before building
**When:** before / during Wednesday 2026-09-09
**Output:** answers to §8's open questions. No code.

Bring to the meeting:

1. The three-dimension table (§3) as the architecture slide.
2. The detect-vs-condition framing (§2).
3. The Helsinki ↔ GPT-model mapping table (§3), with its imperfection stated.
4. Flower & Hayes Figure 2 (embedding inside one sentence) as the evidence for
   why we will not build a stepper UI.

Ask her:

- **Q1** — Should the Ghost baseline get an "insert into draft" affordance?
  (See §8 Q1. This is a measurement-validity question, and it is her call.)
- **Q2** — What format will the per-activity heuristics arrive in? Prose we
  paste into a prompt field, or structured rules? This determines the shape of
  `AIRole`'s activity columns.
- **Q3** — Should the writer be able to *declare* their current activity, or
  only have it detected? (§6 Phase 2 assumes yes; it is cheap and it gives us
  classifier ground truth, but it changes the student UI.)
- **Q4** — For the upcoming user test: how many participants, and do we need
  the role dimension live for it, or is activity-conditioned Tutor enough?

---

### Phase 1 — The seam
**Goal:** roles become data. Behaviour is byte-for-byte identical to today.
**Visible change:** none.
**Why first:** it is the client's actual constraint, and everything else builds
on it.

**Backend**

- [ ] Add `AIRole` model (§5.1) with versioning fields.
- [ ] Seed two roles on first boot, mirroring today's two arms exactly:
      *Socratic Tutor* (`archetype=tutor`, `behaviour=socratic_questioning`,
      `may_produce_prose=false`, `enforcement_level=2`, `base_prompt` =
      current `BASE_SYSTEM_PROMPT`) and *Ghost baseline*
      (`archetype=ghost`, `behaviour=direct_generation`,
      `may_produce_prose=true`, `enforcement_level=0`, `base_prompt` =
      current `CONTROL_SYSTEM_PROMPT`).
- [ ] `ExperimentArm`: add `role_id`; migrate `guardrail_strictness` →
      role reference; keep the column until Phase 3 for rollback safety.
- [ ] `ConversationTurn`: add `role_version_id`.
- [ ] Rename `guardrail_verifier` → `role_arbiter`, `socratic_engine` →
      `response_engine` in `nodes.py`, `runner.py`, `chat.py`, `GRAPH_SPEC`.
- [ ] `build_system_prompt()` reads `AIRole` instead of module constants.
- [ ] `agency_enforcer` gates on `role.may_produce_prose` /
      `role.enforcement_level` rather than `strictness`, and **always runs and
      always logs**, including for the Ghost.
- [ ] CRUD endpoints for roles under `/api/research/roles`, with edit creating
      a new version rather than mutating.

**Frontend**

- [ ] `ConditionCard`: the guardrail dropdown becomes a role picker.
- [ ] Types: `Arm.guardrail_strictness` → `Arm.role_id`; add `AIRole` type.

**Acceptance**

- The five-node trace still renders, with the two new node names.
- A turn under *Socratic Tutor* produces the same system prompt as today
  (assert on the composed string in a test).
- Editing a role creates a new version row; the old row is untouched.
- `agency_enforcer` emits telemetry in the Ghost arm, where it currently emits
  none.

---

### Phase 2 — Activity-conditioned behaviour + the Monitor
**Goal:** client request #1. The Tutor behaves differently in each activity.
**Visible change:** yes — this is the client-facing deliverable.

**Backend**

- [ ] `build_system_prompt()` takes `activity` and appends
      `role.<activity>_prompt`.
- [ ] `TurnState.cognitive` is read by `role_arbiter` and `response_engine`,
      not just written to the DB.
- [ ] Draft per-activity fragments for the Socratic Tutor (see §7.2 for the
      theoretical grounding of each). These are placeholders until Florence's
      heuristics arrive — the point of Phase 1 is that swapping them needs no
      deploy.
- [ ] `TurnRequest` accepts a `declared_activity`; store both declared and
      detected on the turn.
- [ ] Extend the `echo` provider to produce role-appropriate and
      activity-appropriate output, so the offline demo still holds.

**Frontend**

- [ ] A writer-facing activity control in the workspace — *"what are you doing
      right now?"* — Planning / Translating / Reviewing. Externalises Flower &
      Hayes' **Monitor** (§7.2).
- [ ] Show detected vs declared when they disagree (small, non-nagging).
- [ ] Timeline gains a declared-activity track alongside the detected one.

**Acceptance**

- The same question asked while declared *planning* and while declared
  *reviewing* produces materially different replies under the same role.
- Declared and detected activity are both in `export.json`.
- No stepper, no ordering, no completion state anywhere in the UI (§3).

---

### Phase 3 — Measurement correctness & research integrity
**Goal:** the instrument produces data we can publish.
**Must land before the user test.** These are not polish.

- [ ] **Add an `other` activity label.** The C&C paper's Figure 5 has four
      categories and their annotators used the fourth. `_cognitive_fallback()`
      currently returns `"planning"` for anything unmatched, silently inflating
      the rarest category. (§9 D3)
- [ ] **Exclude Reviewing outputs from retention.** The paper's footnote 18 is
      explicit that reviewing responses are not intended to enter the draft.
      `agency_report()` currently joins *all* AI turns into one blob. (§9 D4)
- [ ] **Report retention per activity.** Once the above lands, an
      arms × activities × retention table extends the paper's Figure 7b into a
      comparison the paper could not make.
- [ ] **Fix telemetry participant attribution.** `research.py` `record_event`
      files every event under the first student in the table. (§9 D2)
- [ ] **Capture writer goals.** A short, revisable goal field per workspace.
      Flower & Hayes' third claim is that writing is goal-directed and that
      goal-setting is central to "being creative". We store a plot seed but no
      goals. (§7.2)
- [ ] Fold the half-dead `PromptConfig` into the role registry — two config
      paths is one too many.
- [ ] Housekeeping carried from the last review: broken `/research` link in the
      workspace header, stale route in `run.sh`, stale paths in the README's
      HLD mapping table, `gemini-3.5-flash` vs `gemini-2.5-flash` mismatch
      between `config.py` and `docker-compose.yml`, README's claim that a key
      is already in `backend/.env` (it is gitignored).

**Acceptance**

- Two participants writing simultaneously produce correctly attributed events.
- Retention figures change (they will) and the change is documented.
- `export.json` schema version bumped.

---

### Phase 4 — Deferred, and deliberately so

Not in this iteration. Recorded so we do not drift into them.

- **Do not implement all the roles.** Florence says twice that the Tutor alone
  is sufficient. One rough *Partner* preset is a good demo that the seam works;
  nothing more.
- **Do not model chat practices as configuration.** Chat-to-Generate / Create /
  Chat is a descriptive lens for the writeup and for Q1. It is not a setting.
- **Do not make the role switch per-turn.** The literature says roles blur in
  practice, but a role that changes mid-session destroys attribution of outcomes
  to a condition. Fix the role per arm; measure drift in the *human's* behaviour
  instead.
- **Do not remove the Helsinki machinery.** It becomes the Tutor's behaviour
  implementation and the observed-human-role signal. It stops being the
  architecture, but it does not stop being used.
- Sub-process granularity (generating / organizing / goal-setting within
  Planning; evaluating / revising within Reviewing) — theoretically right,
  premature until we see whether the three-way labels are even reliable.

---

## 7. Literature grounding

### 7.1 Sources

| Short name | Full reference | Local file |
|---|---|---|
| **C&C '24** | Chakrabarty, Padmakumar, Brahman & Muresan. *Creativity Support in the Age of Large Language Models: An Empirical Study Involving Professional Writers.* C&C '24. [doi:10.1145/3635636.3656201](https://doi.org/10.1145/3635636.3656201) | `3635636.3656201.pdf` |
| **F&H 1981** | Flower & Hayes. *A Cognitive Process Theory of Writing.* CCC 32(4), 365–387. | `Flower-CognitiveProcessTheory-1981.pdf` |
| **S&L 2025** | Steinhoff & Lehnen. *Schreiben mit Künstlicher Intelligenz: Das GPT-Modell (Ghost, Partner, Tutor).* Leseräume Jg. 12, H. 11. | `Steinhoff-Lehnen-2025-LR-JG12-H11.pdf` |

> PDFs are gitignored (`*.pdf`) — ACM copyright on C&C '24, client contact
> details in the HLD. Cite by DOI, keep the files local.

### 7.2 What each paper obliges us to do

**F&H — activities are embedded and recursive, not sequential.**
*"People do not march through these processes in a simple 1, 2, 3 order."*
Processes are *"hierarchically organized, with component processes embedded
within other components"*, and a process can recurse inside itself. Figure 2
shows plan→translate→review cycling inside one sentence.
→ **No stepper UI. Ever.**

**F&H — the Monitor.**
A fourth component we currently drop entirely: *"a writing strategist which
determines when the writer moves from one process to another."*
→ Letting the writer **declare** their activity externalises the Monitor. Three
payoffs: ground truth to validate our classifier against (nothing currently
tells us whether the two-word Gemini classification is any good, and it drives
our headline charts); pedagogical value in its own right; and it makes
non-linearity visible to the student, not just the researcher.

**F&H — goal-setting.**
Planning decomposes into *generating*, *organizing* and *goal-setting*. F&H
single out the third as *"little-studied but major"*, and conclude that
*"the act of defining one's own rhetorical problem and setting goals is an
important part of being creative."*
→ We store a plot seed but no goals. Phase 3 adds them. A Tutor that can hold
the draft against the writer's stated goal is a much better Tutor.

**F&H — what Translating actually is.**
Turning meaning *"embodied in key words and organized in complex networks of
relationships"* into linear prose, while juggling constraints that *"interfere"*
with the writer.
→ Phase 2's translating fragment should name the jamming constraint and offer a
procedure — not just decline more politely.

**C&C '24 — the per-activity retention asymmetry.**
9 of the 10 highest-retention instructions are **translation**; 7 of the 10
lowest are **high-level planning** which *"the writer might consider and then
reject."*
→ Translating is our highest-risk activity: it is where students most want help
and where a flat refusal costs the most. Planning's low retention is *not* a
failure — it is evidence that planning help is genuinely deliberative, which is
where a Socratic Tutor should be strongest. Both facts belong in the Phase 2
fragments.

**C&C '24 — footnote 18.**
*"We only calculate the same for Planning and Translation instructions since
text generated in response to Reviewing instructions is not intended to be
included in the draft."*
→ Our `agency_report()` joins **all** AI turns before computing ROUGE-L, so
critique text inflates the denominator by an unknown amount. This makes our
numbers **not** comparable to the Figure 7 baseline we claim comparability with.
Phase 3 fixes it.

**C&C '24 — the fourth label.**
Figure 5 has four categories: Other, Reviewing, Planning, Translation.
→ We force three. Phase 3 adds `other`.

**S&L — prototypicality.**
The Venn diagram is deliberate: roles *"are not sharply separable but form
intersections"*, and the model's job is to **locate** phenomena "in one circle or
between two or three." Their Costello example has the AI moving between Partner
and Tutor within one conversation.
→ Named presets yes; role-as-ground-truth no. Configure the role, measure the
drift.

**S&L — what distinguishes Tutor from Ghost.**
In tutorial co-activity the solution *"remains predominantly with the learner"*,
whereas in Chat-to-Generate *"the solution to the whole problem is left to the
AI"* — *"though the transitions can be fluid."*
→ This is our Helsinki instrumental/executive distinction, arriving from a
different literature. Good corroboration for the meeting.

**S&L — the AI Ghostwriting Effect.**
Draxler et al. (2024), via S&L §2.1: participants claimed authorship of texts
*even when they reported no sense of ownership* — even having contributed
almost nothing.
→ Direct empirical support for why an always-visible agency meter is the right
design, and for why the metric must be honest rather than flattering.

**S&L — Tekin's four evaluator functions.**
Correction, error analysis, evaluation, and *weighing* (judging the
appropriateness of a formulation).
→ A ready-made behaviour taxonomy for the Tutor's **reviewing** fragment. We do
not have to invent one.

**S&L — Fok & Weld's partner subprocesses.**
Ideation, Continuation, Elaboration, Rewriting, Questioning — with limitations
Hallucination, Inconsistent content/style, Repetition, Mediocrity, Ethical
concerns.
→ Useful if and when a Partner role is built (Phase 4). Note the overlap with
C&C '24 Table 8, which we already encode as four named failure modes in
`BASE_SYSTEM_PROMPT`.

---

## 8. Open questions & decisions

Update this table as things get settled. `?` = unresolved.

| # | Question | Status | Notes |
|---|---|---|---|
| **Q1** | Should the Ghost baseline get an "insert into draft" affordance? | **?** — ask Florence | Our app is structurally **Chat-to-Create**; an honest Ghost baseline is **Chat-to-Generate**, which needs an insert path to be itself. Without one, the Ghost arm forces copy-paste or retyping that the Tutor arm never imposes — asymmetric friction that **inflates measured agency in the control arm** and biases the comparison in the intervention's favour. Either give it the affordance and accept the app's character changes, or document the friction as a known limitation. Her call, not ours. |
| **Q2** | What format will the per-activity heuristics arrive in? | **?** | Determines whether `AIRole`'s activity columns are free text or structured. |
| **Q3** | Writer-declared activity — in or out? | **?** | Phase 2 assumes in. Cheap, gives classifier ground truth, changes student UI. |
| **Q4** | User-test scale, and is the role dimension needed live for it? | **?** | Affects whether Phase 1 must ship before the test or only Phase 2. |
| **D1** | Roles and arms become append-only-on-edit | **decided** | See §9 D1. Non-negotiable once heuristics are editable. |
| **D2** | Keep `guardrail_strictness` column through Phase 2 | **decided** | Rollback safety. Drop in Phase 3. |
| **D3** | Do not build all roles this iteration | **decided** | Client said Tutor is sufficient, twice. |

---

## 9. Pre-existing defects this iteration absorbs

Found in the 2026-09-07 read-through. Listed here because Phase 3 fixes them and
because two of them corrupt research data.

| # | Severity | Defect |
|---|---|---|
| **D1** | **high** | `experiments.update_arm()` mutates arms in place and logs only the *names* of changed fields, not values. Turns record `arm_id` but no version. Edit a condition mid-study and the data cannot distinguish before from after. Our own code comment says conditions exist so results are not *"a config file someone edited last Tuesday"* — but that is exactly what can happen today. Latent now; **fatal** once roles and per-activity prompts are editable by design. |
| **D2** | **high** | `research.py` `record_event` resolves the user with `select(User).where(User.role == "student")` — the *first* student in the table — ignoring the `X-User-Id` header the browser sends. Every keystroke, paste and export event from the whole cohort is filed under one participant. Invisible in a single-user demo; silently corrupts the user-test dataset. |
| **D3** | medium | `_cognitive_fallback()` returns `"planning"` for anything unmatched, inflating the category the paper says is rarest. Compounded by forcing a three-way choice where the paper uses four. |
| **D4** | medium | `agency_report()` computes ROUGE-L over *all* AI turns, contradicting C&C '24 footnote 18 and breaking the comparability claim we make in the README and the Data page footer. |
| **D5** | low | Researcher Data page: the scope filter passes `scope` to `events` and `timeline`, but `api.summary()` takes no workspace argument — so the two charts under *"across the current scope"* silently stay cohort-wide, as does the sessions table. |
| **D6** | low | `frontend/app/student/story/[id]/page.tsx:245` links to `/research`, which does not exist (route is `/researcher`), and a student would be bounced by `PortalGuard` anyway. Arguably the link should not be in the student portal at all. |
| **D7** | low | `run.sh:32` prints the stale `/research` route. README's HLD mapping table points at `frontend/app/story/[id]/page.tsx`, `app/research` and `/researcher/telemetry` — none of which exist. |
| **D8** | low | `config.py` defaults to `gemini-3.5-flash`; `docker-compose.yml` defaults to `gemini-2.5-flash`. Container and local demos run different models. |
| **D9** | low | README says *"A Gemini key is already in `backend/.env`"*, but `.env` is gitignored — anyone cloning the group repo gets the offline scaffold and a README that contradicts it. |
| **D10** | trivial | `_split_probes()` has a no-op ternary: `p if p.endswith("?") else p`. Unused `PortalLoading` import in the workspace page. |

---

## Appendix A — File change map

Rough guide to blast radius. `+` new, `~` modified, `→` renamed.

```
backend/app/
  models.py            ~ AIRole (new entity); ExperimentArm.role_id;
                         ConversationTurn.role_version_id; StoryWorkspace.goals
  prompts.py           ~ constants become seed data; build_system_prompt()
                         takes activity + reads role record
  schemas.py           ~ RoleIn/RoleOut; TurnRequest.declared_activity
  metrics.py           ~ per-activity retention; exclude reviewing (D4)
  graph/
    state.py           ~ role fields on TurnState
    nodes.py           ~ guardrail_verifier → role_arbiter
                         socratic_engine   → response_engine
                         agency_enforcer contract-relative
                         _cognitive_fallback gains "other" (D3)
    runner.py          ~ GRAPH_SPEC node ids and labels
  providers/echo.py    ~ role- and activity-aware offline output
  routers/
    chat.py            ~ role resolution replaces strictness resolution
    experiments.py     ~ versioned writes (D1)
    research.py        ~ + /roles CRUD; fix record_event attribution (D2)
    workspaces.py      ~ goals field

frontend/
  lib/types.ts         ~ AIRole; Arm.role_id; declared activity
  lib/api.ts           ~ role endpoints
  components/
    ConditionCard.tsx  ~ guardrail dropdown → role picker
    RoleEditor.tsx     + per-activity prompt editing
    ActivityControl.tsx+ writer-declared activity (the Monitor)
    CognitiveTimeline  ~ declared vs detected track
  app/student/story/[id]/page.tsx  ~ activity control; fix /research link (D6)
  app/researcher/page.tsx          ~ roles section
```

---

## Appendix B — Glossary

Terms from three literatures that mean adjacent things. Kept straight here so
the code and the client meeting use the same words.

| Term | Source | Means |
|---|---|---|
| Planning / Translating / Reviewing | F&H 1981 | The three writing activities. Non-sequential, embedded, recursive. |
| Monitor | F&H 1981 | The writer's strategist deciding when to switch activities. |
| Ghost / Partner / Tutor | S&L 2025 | Roles the **AI** plays. |
| Client / Explorer / Learner | S&L 2025 | Corresponding roles the **human** plays. |
| Chat-to-Generate / -Create / -Chat | S&L 2025 | Chat practices. Story Studio is Chat-to-Create. |
| Executive / instrumental help-seeking | Nelson-Le Gall, via HLD | Whether the learner offloads the work or gets help doing it. |
| Agency ratio | ours (HLD 10.2) | 1 − (draft 5-grams also in AI output) ÷ draft 5-grams. |
| AI retention | C&C '24 Fig. 7 | ROUGE-L recall of AI output within the draft. |
| Arm / condition | ours | A bundle of every manipulable variable, assigned to participants. |

> **Terminology note.** F&H and the client write *"Translating"*; C&C '24 writes
> *"Translation"*; our DB stores `translation` and our UI says `translating`.
> Pick one for the research instrument. Recommend **`translating`** in UI copy
> (matches the client) and keep `translation` as the stored value to avoid a
> migration — but document the mapping in the export schema.

# How Story Studio works — in plain terms

A walkthrough of what happens behind the chat box: the pipeline, the
guardrails, AI roles, the writing-activity Monitor, and what gets recorded.
Written for people who don't read the code. File and function names are in
`code font` for anyone who wants to look.

Throughout, one running example — the student types:

> **"Just write the next paragraph for me."**

---

## 1. The big picture

Think of the AI as a **writing centre with a strict policy**: the tutor helps
you write, but never writes *for* you.

Behind the chat box, every message goes through **six stations**, like an
assembly line. Each station does one job and passes a note to the next.

```mermaid
flowchart TD
    S([Student's message]) --> R
    R["1. Receptionist<br/><i>What kind of help is this?</i>"] --> M
    M["2. Monitor<br/><i>Planning, drafting or revising?</i>"] --> A
    A["3. Manager<br/><i>Build the tutor's instructions</i>"] --> T
    T["4. Tutor (Gemini)<br/><i>Writes the reply</i>"] --> F
    F["5. Tidier<br/><i>Cleans up the format</i>"] --> I
    I["6. Inspector<br/><i>Did it break the rules?</i>"] --> O([Reply shown to student])

    style R fill:#e8eef7,stroke:#27477a
    style M fill:#e8eef7,stroke:#27477a
    style A fill:#e8eef7,stroke:#27477a
    style T fill:#fdf5e3,stroke:#a1620a
    style F fill:#e8eef7,stroke:#27477a
    style I fill:#fde8e8,stroke:#b91c1c
```

| # | Station | In the code |
|---|---|---|
| 1 | Receptionist | `intent_classifier` |
| 2 | Monitor | `activity_monitor` |
| 3 | Manager | `role_arbiter` |
| 4 | Tutor | `response_engine` |
| 5 | Tidier | `response_formatter` |
| 6 | Inspector | `agency_enforcer` |

All six live in `backend/app/graph/nodes.py`.

---

## 2. Station by station

### 1 · Receptionist — "What kind of help is this?"

Sorts the request into one of four types (the Helsinki help-seeking model):

| Type | Means | Example |
|---|---|---|
| **Executive** | "Do it for me" | *"Write the next paragraph"* |
| **Instrumental** | "Help me do it myself" | *"How do I build tension?"* |
| **Brainstorm** | "Give me options" | *"What could happen next?"* |
| **Reflection** | Thinking aloud | *"I think she should fail"* |

It first does a quick **keyword check** for blatant cases ("write the…",
"rewrite…", "finish this…"). That also acts as a safety net that works even if
Gemini is down. Then a small, fast Gemini model gives the final label.

**Our example → Executive.**

### 2 · Monitor — "Planning, drafting or revising?"

Flower & Hayes' model of writing has three activities — **Planning**,
**Translating** (turning ideas into sentences) and **Reviewing** — and a
"Monitor" that decides which one the writer is in. Here, **the system is the
Monitor**. Neither the student nor the researcher picks the activity.

```mermaid
flowchart LR
    subgraph Context["What the Monitor reads"]
        a[The student's message]
        b[The story so far]
        c[How much the story grew<br/>or shrank since last time]
        d[The recent chat]
        e[The student's brief idea]
        f[Highlighted passage]
        g[Its own previous decision]
    end
    Context --> G{{Gemini judges}}
    G --> P[Planning]
    G --> Tr[Translating]
    G --> Rv[Reviewing]
    G -. also records .-> Why["a confidence score<br/>and a one-line reason"]
```

It reads the **whole situation**, not just keywords. *"thanks"* means nothing
alone, but after the student just wrote two new paragraphs, it probably means
they're drafting.

There is **no order** — any activity can follow any other, because real
writers jump around.

**Backup plan:** if Gemini can't answer (offline, out of quota), a simple
points-based rule decides instead — e.g. "almost empty page → planning", "text
just grew → translating", "asking about a highlighted passage → reviewing".
That rule is also run silently every time, so researchers can compare it with
Gemini's judgement.

**Our example → probably Translating** ("stuck turning a scene into
sentences").

Code: `backend/app/graph/monitor.py`; the Monitor's instructions are
`MONITOR_SYSTEM_PROMPT` in `backend/app/prompts.py`.

### 3 · Manager — "Build the tutor's instructions"

Stacks together the instructions for *this one reply*, like building a
sandwich (see §3 for the full picture).

### 4 · Tutor — writes the reply

Gemini (`gemini-3.5-flash`) receives the instructions plus the story and writes
a reply. If Gemini fails, a built-in offline tutor answers instead so the app
never breaks.

### 5 · Tidier — cleans up the format

Pulls out the reply and its follow-up questions into a clean shape, even if
Gemini ignored the requested layout.

### 6 · Inspector — the last line of defence

AI models don't always follow instructions (small ones often just start
writing the story). So after the tutor replies, the Inspector checks the
**actual text**:

| Check | What happens |
|---|---|
| Slipped in quoted dialogue? | Stripped |
| "*Here's an example:*" / "*something like…*"? | Cut from that point |
| Narrating the story in past tense, using the student's own character names, asking nothing? | Replaced with *"I started writing the scene there, which isn't mine to write."* |
| A long block of text with no question in it? | Cut to two sentences |

**Our example:** the tutor declined in one line and asked something like
*"What does Idris do with his hands while he decides whether to open it?"* —
nothing to remove.

---

## 3. What the tutor actually receives

The tutor **does not** read notes from the Receptionist or the Monitor
directly. The **Manager turns their decisions into instructions**, and the
tutor only sees those, plus the story.

```mermaid
flowchart TD
    Role["AI Role<br/>(Tutor or Ghost)"] -->|main instructions| SYS
    Mon["Monitor's decision<br/>(e.g. Translating)"] -->|matching phase tip| SYS
    Rec["Receptionist's label"] -->|only if 'Executive':<br/>intercept note| SYS
    Cond["Condition settings"] -->|strictness + length| SYS

    SYS["<b>Instructions</b><br/>(system prompt)"] --> GEM{{"Tutor (Gemini)"}}

    Story["The story so far"] --> USR
    Chat["Recent chat"] --> USR
    Sel["Highlighted passage"] --> USR
    Idea["Student's brief idea"] --> USR
    Msg["The student's message"] --> USR
    USR["<b>Material to respond to</b><br/>(user prompt)"] --> GEM

    GEM --> Reply([Reply → Tidier → Inspector])

    style SYS fill:#e8eef7,stroke:#27477a
    style USR fill:#fdfdfb,stroke:#5b6473
    style GEM fill:#fdf5e3,stroke:#a1620a
```

**The instructions, stacked in order:**

```
┌──────────────────────────────────────────────────────────┐
│ 1. Role's main instructions                               │
│    "You are a Socratic writing partner… you never write   │
│     their story… reply with questions and observations."  │
├──────────────────────────────────────────────────────────┤
│ 2. Phase tip   (from the Monitor)                         │
│    Translating: "name what's jamming the sentence, give   │
│    a method, never the words."                            │
├──────────────────────────────────────────────────────────┤
│ 3. Intercept note   (only if the request was Executive)   │
│    "Decline in one short line, then ask the question      │
│    that lets them write it themselves."                   │
├──────────────────────────────────────────────────────────┤
│ 4. Strictness note   (Tutor at level 2)                   │
│    "Not even illustrative fragments in quotes."           │
├──────────────────────────────────────────────────────────┤
│ 5. Length setting   (light / balanced / deep)             │
└──────────────────────────────────────────────────────────┘
```

**What the tutor never sees:**

- The Receptionist's label itself. Only its "Executive" result gets through
  (as the intercept note); "Instrumental", "Brainstorm" and "Reflection" change
  nothing — they're recorded for research only.
- The Monitor's reason or confidence — only the phase gets through, as the
  matching tip.
- Anything about the experiment — which condition, what's being measured.

---

## 4. Guardrails — three layers, not one

"The guardrail" is really three separate protections at different moments:

```mermaid
flowchart LR
    Q([Student asks]) --> L2
    L2{"Layer 2 — Intercept<br/>Is this 'do it for me'?"} -- yes --> N["Add the<br/>'decline + ask' note"]
    L2 -- no --> L1
    N --> L1
    L1["Layer 1 — The rule<br/>'Never write their story'<br/>(in every instruction)"] --> G{{Gemini writes}}
    G --> L3{"Layer 3 — Inspector<br/>Did prose slip through?"}
    L3 -- yes --> X["Strip / replace it<br/>(and log that it happened)"]
    L3 -- no --> OK([Reply shown])
    X --> OK

    style L1 fill:#e8eef7,stroke:#27477a
    style L2 fill:#fdf5e3,stroke:#a1620a
    style L3 fill:#fde8e8,stroke:#b91c1c
```

| Layer | When it acts | Like… |
|---|---|---|
| **1. The rule in the instructions** | Before Gemini writes | The staff handbook: "never write their story" |
| **2. The intercept** | When a "do it for me" request is spotted | A manager saying "this one's asking for the answer — redirect them" |
| **3. The Inspector** | After Gemini writes | Quality control checking the finished product |

Layer 1 usually works on its own — but AI is unreliable, so layers 2 and 3 are
there for when it doesn't. Every Inspector action is logged, so researchers can
see how often the AI *tried* to break the rule.

---

## 5. AI roles — which job the AI is playing

A **role** is the AI's job description, from Steinhoff & Lehnen's model:
**Ghost** (writes for you), **Partner** (brainstorms with you), **Tutor**
(helps you learn to do it yourself).

```mermaid
flowchart LR
    subgraph Tutor["Socratic Tutor"]
        t1["Asks questions,<br/>never writes the story"]
        t2["Strictness 2:<br/>Inspector fully on"]
        t3["Different tips for planning,<br/>translating, reviewing"]
    end
    subgraph Ghost["Ghost baseline"]
        g1["Ordinary AI assistant:<br/>writes whatever you ask"]
        g2["Strictness 0:<br/>Inspector only logs"]
        g3["No phase tips"]
    end
    Tutor -. "the intervention" .-> E((Experiment))
    Ghost -. "the comparison group" .-> E
```

| | **Socratic Tutor** | **Ghost baseline** |
|---|---|---|
| Job | Ask questions, never write the story | Write whatever is asked |
| May write prose? | No | Yes |
| Strictness | 2 — Inspector fully on | 0 — Inspector only logs |
| Phase tips | Planning / Translating / Reviewing | None |
| Purpose | The actual intervention | The **control** to compare against |

**Roles are data, not code.** A researcher edits them in the portal
(Researcher → Study → AI roles) — no programmer, no restart.

**Every edit creates a new version** instead of overwriting the old one, and
every reply records which version produced it:

```mermaid
flowchart LR
    v1["Tutor v1<br/>original tips"] -->|researcher edits<br/>planning tip| v2["Tutor v2<br/>new planning tip"]
    v2 -->|edits again| v3["Tutor v3"]
    r1(["Replies from<br/>week 1"]) -.->|produced by| v1
    r2(["Replies from<br/>week 2"]) -.->|produced by| v2
```

So if Florence changes the planning tip halfway through the study, you can
still tell exactly which replies came from which wording.

---

## 6. Conditions — how the experiment is set up

A **condition** is one arm of the experiment: a bundle of settings.

```mermaid
flowchart TD
    subgraph C1["Condition: Socratic guardrail"]
        c1r[Role: Socratic Tutor]
        c1m[Model: Gemini]
    end
    subgraph C2["Condition: Unguarded assistant (control)"]
        c2r[Role: Ghost baseline]
        c2m[Model: Gemini]
    end
    P1([Student A]) --> C1
    P2([Student B]) --> C2
    P3([Student C]) --> C1
    C1 --> RES
    C2 --> RES
    RES["Results page<br/>compares the groups"]
```

Students are assigned by hand or at random. The results page then compares
the groups on the same measures:

- **Human agency** — how much of the story is the student's own words
- **AI retention** — how much AI-written text ended up in the story
- **Intercept rate** — how often "do it for me" requests were caught
- words per exchange, draft length, response time

That's the "if we change X, do students do Y?" question.

---

## 7. What the student sees vs what's recorded

```mermaid
flowchart LR
    subgraph Student["What the student sees"]
        s1[Their story]
        s2[A friendly chat]
    end
    subgraph Behind["Recorded on every message"]
        b1[Help type<br/>executive / instrumental / …]
        b2[Detected activity]
        b3[Monitor's decision + reason]
        b4[Which role version answered]
        b5[Was it intercepted?]
        b6[What the Inspector removed]
        b7[Highlighted passage]
        b8[Response time]
    end
    Behind --> R["Researcher portal<br/>+ anonymised exports<br/>(names → Participant_07)"]
```

The student never sees labels, phases, scores or research settings — only their
story and the conversation.

---

## 8. The whole thing in one sentence

> The student asks something → the system works out **what kind of help** they
> want and **what stage of writing** they're in → builds instructions for the
> AI according to its **role** (Tutor or Ghost) → the AI replies → an
> **Inspector** double-checks it didn't write the story for them → and every
> step is quietly recorded for the research.

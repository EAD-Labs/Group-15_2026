# Updates — after Florence's heuristic evaluation (13 Oct 2026)

What changed and why, in plain words. Every item below was **checked**: in the browser, by automated tests (93 pass), or by running real questions through Gemini and the local Ollama model.

✅ = fixed and verified · ⚠️ = works, but with a known limit

---

## 1. Interface (what Florence hit)

| Problem | What we changed | Checked how | |
|---|---|---|---|
| Changing the title → error, stuck on an error page | A failed save no longer crashes the page. It says "Not saved yet – retrying…" and saves by itself once the server answers | Made every save fail on purpose: no error page, and the title saved on its own once saving worked again | ✅ |
| Title can be emptied | An empty title is refused and the old one kept, with a short note | Browser | ✅ |
| No undo / no way back | New **"Earlier versions"** button: see older versions of the story and restore one. Restoring keeps a copy of the current text, so you can undo the restore | Browser: edited, restored, then saw the replaced text listed to go back to | ✅ |
| "Hamburger menu does nothing" | It was focus mode. Removed; toolbar buttons now have words, not mystery icons | Browser | ✅ |
| Partner's reply looks like a quotation | Replies are now normal message bubbles | Browser (day + night) | ✅ |
| Night mode: chat and story blur together | Chat panel gets its own clearly different colour | Browser | ✅ |
| Chat always open (may push AI use) | Chat can be hidden/shown. Whether it **starts** open is a study-condition setting. Hide/show is logged | Browser + event log | ✅ |
| "The words stay yours" primes students | Removed. Partner introduced neutrally. Same fix on the landing page (it said "a partner that will not write your story") | Browser | ✅ |
| Title asked first, "who is my partner?" | New story: what it's about → first line → title (optional). One line explains the partner | Browser | ✅ |

## 2. How the AI answers

| Problem | What we changed | Result | |
|---|---|---|---|
| Spelling/simple questions got a question back | System spots questions with one right answer → AI answers directly | Gemini: spelling, meaning, grammar all answered correctly | ✅ |
| Doesn't answer what was asked; all replies alike | New rule: answer first, then at most one question | Gemini follows it | ✅ |
| Quietly picks a story direction ("more conflict") | AI offers 2–3 options side by side, or asks which the writer wants | Gemini on "How do I structure my story now?" gives three different structures and asks which fits, close to Florence's own suggested reply | ✅ |
| "Write me an alternative sentence" → just a question | Short "the wording should come from you" + concrete help (what the line must do, choices, approaches) | Gemini | ✅ |
| AI's best question was invisible | A layout leftover hid it; fixed | Test | ✅ |
| Safety filter gaps (prose slipping through; good help being cut) | Rebuilt: removes only the story sentences and keeps the help around them | Tests built from real model replies; no false cuts on 32 good Gemini replies | ✅ |

The old AI behaviour is kept unchanged as Tutor **v1**; the new one is Tutor **v2**. Past data still points to the exact version that produced it.

## 3. Research data you can trust

| Risk | What we changed | |
|---|---|---|
| Model failed → canned offline reply shown silently | Per condition: **show "unavailable"** (default, nothing substituted) or **use backup, flagged**. Tested with a real outage: the student sees "No reply – your partner was unavailable" | ✅ |
| Gemini quietly switched to another model when out of quota | Every reply records which model was asked for vs which answered. Under "show unavailable" it never switches | ✅ |
| No overview of the above | New **Delivery fidelity** panel (researcher → Data): per participant, how many replies came from the intended model | ✅ |
| Editing a condition overwrote it | Every edit is a new version; each reply records its version | ✅ |
| A global setting could override conditions (even the control) | Removed | ✅ |
| Control group's backup showed a made-up story paragraph | Removed | ✅ |
| Enforcer threw away what the model actually said | Original kept for the researcher whenever the enforcer changes a reply | ✅ |

## 4. Model comparison (same 10 test questions, from Florence's own list)

| | Gemini | Local Ollama (qwen2.5:3b, what Florence used) |
|---|---|---|
| Replies meeting all checks | **9/10** (1 = free-tier quota ran out) | **6/10** |
| Gets the type of help right | 10/10 | 10/10 |
| Wrong facts | none | ⚠️ yes ("accommodate has one m", "who" instead of "whom") |
| Tries to write the story | no | ⚠️ sometimes (filter catches most, not all) |
| Time per reply | ~5–12 s | ~7–12 s |

Full replies: `docs/eval/final-2026-10-13.md`. Re-run any time: `backend/eval/suite.py`.

**Bottom line:** Florence's generic, repetitive replies were partly our design (fixed) and partly the small local model (not fixable by us). **Don't run the pilot on qwen2.5:3b.**

## Decisions for Florence (Wednesday)

1. **Pilot model:** Gemini (best) or a bigger local model? The 3B one gives wrong answers.
2. **Free-tier Gemini quota runs out within a day of testing.** With "show unavailable" (the safest choice for the study), a pilot needs a paid key. Or accept "use backup, flagged".
3. Should the chat **start open or hidden**? Either works; it must be the same for everyone in a group.
4. Direct answers: spelling, grammar, word meanings only? (Full alternative sentences stay off-limits.)
5. Could she send the title-error screenshot? We fixed the crash itself but couldn't reproduce her exact trigger.

# VOXPREP — Guardrails, Do's, Don'ts & Fallbacks

> This file governs both human team members AND any AI agent (Antigravity) working on this project.  
> When in doubt — **stop and read this file before writing code.**

---

## 🤖 AI Agent (Antigravity) Guardrails

### ✅ AI Agent DO's
- Read `03_PHASE_PLAN.md` before writing any code to confirm which phase is active.
- Only build features listed as ✅ MVP in `04_MVP_vs_EXTRA.md`.
- Ask for clarification if a user request seems to add a new feature not in the MVP list.
- Write code that matches the folder structure in `02_TECH_STACK.md`.
- Confirm the API contract with the team before implementing a new endpoint.
- Keep functions small and single-responsibility.
- Add a comment at the top of each new file indicating which phase it belongs to.
- Run tests / health checks after implementing each module.

### ❌ AI Agent DON'Ts
- Do NOT build any Post-MVP feature unless explicitly told "this is now in scope."
- Do NOT change the technology stack without updating `02_TECH_STACK.md` and informing the team.
- Do NOT skip a phase because "it looks simple" — phases must be completed in order.
- Do NOT invent new API endpoints that weren't planned — add them to the docs first.
- Do NOT delete or overwrite existing code without understanding what it does.
- Do NOT commit secrets or API keys to the repository.

### 🔄 AI Agent Fallbacks
| Situation | Fallback Action |
|---|---|
| Feature request is not in MVP list | Say: "This is a Post-MVP feature per `04_MVP_vs_EXTRA.md`. Do you want me to log it for later?" |
| Unclear which phase a task belongs to | Check `03_PHASE_PLAN.md`. If still unclear, ask the team. |
| A task depends on another member's unfinished work | Note the dependency, build a mock/stub, and move on. |
| LLM API call fails | Return a friendly error message, log it, and retry once before surfacing the error to the user. |
| STT fails to transcribe | Display "Could not understand. Please try again." — do NOT guess the content. |
| TTS fails | Fall back to displaying the text response on screen without audio. |
| Supabase query fails | Return a 500 error with a clear message. Do NOT silently fail. |

---

## 🎤 Agent 1 — AI Interviewer Rules

### ✅ Interviewer DO's
- Ask **one question at a time**.
- Listen to the **complete answer** before responding.
- Ask **contextually relevant** follow-up questions based on the specific answer given.
- Maintain a consistent **professional tone** throughout the interview.
- Evaluate answers using the approved **4-dimension rubric** (Relevance, Clarity, Depth, Examples).
- Provide **constructive, specific feedback** in the report — not generic phrases.
- Stay in the **role of a professional interviewer** at all times during the session.

### ❌ Interviewer DON'Ts
- Do NOT reveal the answer or hints before the candidate responds.
- Do NOT ask questions unrelated to the interview topic or the candidate's role.
- Do NOT repeat the same question again (unless the user explicitly asks to repeat).
- Do NOT invent qualifications or experiences the candidate hasn't mentioned.
- Do NOT give arbitrary scores — scores must be based on rubric evaluation.
- Do NOT change the interview format (e.g., switch from HR to Technical) mid-session without user permission.
- Do NOT act like a tutor during the interview — save coaching for the report.
- Do NOT ask more than **1 follow-up per question** in MVP.

### 🔄 Interviewer Fallbacks
| Situation | Fallback |
|---|---|
| Answer is too short / unclear | Ask once: "Could you elaborate on that?" |
| Answer goes completely off-topic | Acknowledge politely and move to the next question |
| Candidate says "I don't know" | Accept it, note it in the evaluation, move to next question |
| Interview exceeds time/question limit | Gracefully conclude: "We've covered our questions. Let me prepare your report." |
| LLM generates a repeated question | Detect duplicates before asking — regenerate if duplicate found |

---

## 🗣 Agent 2 — AI Communication Coach Rules

### ✅ Coach DO's
- Maintain a **natural, friendly, supportive** conversational tone.
- Correct mistakes **politely** — always after the candidate finishes speaking.
- Explain **why** a sentence can be improved (e.g., "This phrase sounds more natural because...").
- Provide a **specific better alternative** for each correction.
- **Adapt difficulty** to the candidate's current level (from their communication profile).
- Remember and build on **approved learning progress** from previous sessions.
- End each session with a **brief positive summary** of what was practiced.

### ❌ Coach DON'Ts
- Do NOT interrupt while the user is still speaking.
- Do NOT correct **every single mistake** — prioritize the most impactful 1-2 corrections per exchange.
- Do NOT use language that makes the user feel **embarrassed or judged**.
- Do NOT give repetitive exercises (check session history to vary content).
- Do NOT **claim to detect confidence or emotions** from voice — only use the text content.
- Do NOT force advanced vocabulary on a beginner user.
- Do NOT stay on the same topic for more than 3 exchanges without progressing.

### 🔄 Coach Fallbacks
| Situation | Fallback |
|---|---|
| User gives a very short one-word answer | Gently prompt: "Can you tell me a bit more about that?" |
| User seems frustrated | Acknowledge warmly: "No worries, let's try something a bit easier." |
| STT produces garbled text | Ask: "Sorry, I didn't quite catch that. Could you say it again?" |
| Session runs long | Coach summarizes progress and offers to end: "We've had a great session! Want to wrap up?" |
| Communication profile not found | Start with beginner defaults, create a new profile |

---

## 🏗 Development Guardrails (Human Team)

### ✅ Team DO's
- Follow the phase order: 0 → 1 → 2 → 3 → 4.
- Tick off acceptance criteria checkboxes as you complete them.
- Keep `main` branch clean — test before merging.
- Communicate immediately when blocked (don't stay stuck silently for > 20 min).
- Update `docs/` if anything changes from the original plan.

### ❌ Team DON'Ts
- Do NOT merge half-finished features to `main`.
- Do NOT build two phases simultaneously.
- Do NOT use a technology not in `02_TECH_STACK.md` without team agreement.
- Do NOT scope-creep — adding a "quick extra feature" during MVP time is forbidden.
- Do NOT deploy to production before Phase 4.

---

## Scope Creep Decision Tree

```
New idea / feature request appears
            │
            ▼
  Is it listed in 04_MVP_vs_EXTRA.md as MVP?
       │                    │
      YES                   NO
       │                    │
       ▼                    ▼
  Is current phase     Is it listed as "If time" (⚡)?
  complete?                │              │
   │       │              YES             NO
  YES      NO              │              │
   │       │               ▼              ▼
   ▼       ▼          Is MVP done?     Log it.
  Build   Finish       │       │       Do NOT
  it.     current     YES      NO      build now.
          phase        │       │
          first.       ▼       ▼
                     Build   Log for
                     it.     Post-MVP.
```


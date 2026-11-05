# VOXPREP — Phase-by-Phase Development Workflow

> 📌 **Rules:**
> - Complete each phase fully before starting the next.
> - Every phase has an **Approval Gate** — check `05_ACCEPTANCE_CRITERIA.md` to pass.
> - If you're unsure whether a feature belongs here, check `04_MVP_vs_EXTRA.md` first.
> - Estimated times assume 2 people working simultaneously.

---

## 🗺 Phase Roadmap Summary

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4
 (Setup)  (Foundation) (Agent 1)  (Agent 2)  (Polish + Deploy)
  ~30min    ~1.5hrs     ~3hrs      ~2.5hrs      ~1hr
```

**Total estimated MVP time: ~8.5 hours**

---

## Phase 0 — Project Setup (⏱ ~30 min)

> **Goal:** Both members have a working local development environment.

### Tasks
- [ ] Create GitHub repository
- [ ] Set up project folder structure (see `02_TECH_STACK.md`)
- [ ] Initialize Next.js frontend (`npx create-next-app`)
- [ ] Initialize FastAPI backend (`pip install fastapi uvicorn`)
- [ ] Set up Supabase project (create tables: `users`, `interview_sessions`, `coach_sessions`)
- [ ] Add `.env` files with API keys
- [ ] Confirm both members can run frontend and backend locally
- [ ] Create a shared Supabase project both can access

### Deliverables
- Running `npm run dev` shows Next.js default page
- Running `uvicorn app.main:app` shows FastAPI running
- Supabase dashboard accessible with tables created

### ⛔ Approval Gate
See: `05_ACCEPTANCE_CRITERIA.md → Phase 0`

---

## Phase 1 — Foundation & Voice Pipeline (⏱ ~1.5 hrs)

> **Goal:** A working voice loop — user speaks, system responds via voice.

### Tasks

#### Backend
- [ ] Create `GET /health` endpoint (ping test)
- [ ] Build `llm.py` — Gemini API wrapper (send prompt → get text response)
- [ ] Build `stt.py` — Audio → Text (use Gemini or Deepgram)
- [ ] Build `tts.py` — Text → Audio (use Web Speech API or basic ElevenLabs)
- [ ] Create `POST /voice/process` endpoint (audio in → text response out → audio)
- [ ] Auth endpoints: `POST /auth/register`, `POST /auth/login`

#### Frontend
- [ ] Landing page with "Start Interview" and "Talk to Coach" buttons
- [ ] Auth pages: Login + Register (connect to Supabase)
- [ ] `VoiceRecorder.tsx` — captures mic audio, sends to backend
- [ ] `VoicePlayer.tsx` — plays back audio response
- [ ] `VoiceVisualizer.tsx` — simple animated waveform while speaking
- [ ] Basic voice test page: user speaks → system responds → plays back

### Deliverables
- User can register/login
- User can speak a sentence, it converts to text, LLM responds, response plays back as audio
- End-to-end voice loop works

### ⛔ Approval Gate
See: `05_ACCEPTANCE_CRITERIA.md → Phase 1`

---

## Phase 2 — Agent 1: AI Interviewer (⏱ ~3 hrs)

> **Goal:** A complete, functional mock interview session with report generation.

### Tasks

#### Backend
- [ ] `agents/interviewer.py` — full Agent 1 logic:
  - Onboarding: collect name, role, experience, interview type
  - Load correct system prompt based on interview type (Technical / HR)
  - Question loop: ask → listen → evaluate → follow-up or next
  - Evaluation rubric per question (Relevance, Clarity, Depth, Examples)
  - Detect end of interview (N questions completed or candidate exits)
- [ ] `services/report.py` — generate structured performance report
- [ ] `routers/interview.py`:
  - `POST /interview/start` — start session, return session_id
  - `POST /interview/respond` — send answer, get next question
  - `POST /interview/end` — close session, trigger report
  - `GET /interview/report/{session_id}` — fetch report
- [ ] Store session data in Supabase `interview_sessions` table

#### Frontend
- [ ] `/interview/setup` page — form: role, experience, interview type
- [ ] `/interview/session` page:
  - Displays current question (text + voice)
  - Voice input button (press and hold / press to toggle)
  - Live transcript of what user said
  - "End Interview" button
- [ ] `/interview/report` page:
  - Overall score
  - Score per dimension (Relevance, Clarity, Depth, Examples)
  - Strengths list
  - Weaknesses list
  - Improvement tips
  - "Try Again" and "Go to Coach" buttons

### Deliverables
- User can complete a full 5-question mock interview (HR or Technical)
- System evaluates each answer
- Report generates and displays after interview

### ⛔ Approval Gate
See: `05_ACCEPTANCE_CRITERIA.md → Phase 2`

---

## Phase 3 — Agent 2: AI Communication Coach (⏱ ~2.5 hrs)

> **Goal:** A working coaching session in at least 2 modes.

### Tasks

#### Backend
- [ ] `agents/coach.py` — full Agent 2 logic:
  - Load user communication profile
  - Mode selection: Conversation Practice, Vocabulary, Answer Training
  - Session loop: coach speaks → user responds → coach corrects politely
  - Adapt difficulty based on user level (beginner/intermediate)
  - Update communication profile after session
- [ ] `routers/coach.py`:
  - `POST /coach/start` — start coach session
  - `POST /coach/respond` — send user response, get coach reply
  - `POST /coach/end` — close session, update profile
- [ ] Store session data in Supabase `coach_sessions` table

#### Frontend
- [ ] `/coach/setup` page — select mode (Conversation / Vocabulary / Answer Training)
- [ ] `/coach/session` page:
  - Coach message displayed + spoken
  - User voice input area
  - Correction display panel (shows what was improved and why)
  - Session progress indicator
  - "End Session" button
- [ ] Dashboard update — show communication profile stats

### Deliverables
- User can run a conversation practice session with the coach
- Corrections are shown after each response
- Communication profile updates after session

### ⛔ Approval Gate
See: `05_ACCEPTANCE_CRITERIA.md → Phase 3`

---

## Phase 4 — Polish, Integration & Deployment (⏱ ~1 hr)

> **Goal:** MVP is live, stable, and presentable.

### Tasks
- [ ] Dashboard page — show past interviews, past coach sessions, communication profile
- [ ] Cross-link: Interview report's "Go to Coach" button routes to relevant coach mode
- [ ] Loading states and error handling on all pages
- [ ] Mobile-responsive layout check
- [ ] Deploy frontend to Vercel
- [ ] Deploy backend to Railway
- [ ] Set all environment variables in production
- [ ] End-to-end smoke test on production URLs
- [ ] Write `README.md` with setup instructions

### Deliverables
- Live production URL works
- All 4 pages functional: Landing, Interview Session, Coach Session, Dashboard
- README written

### ⛔ Approval Gate
See: `05_ACCEPTANCE_CRITERIA.md → Phase 4`

---

## Post-MVP Phases (Do NOT build during MVP sprint)

> These are listed only for future planning. Do not start until instructed.

| Phase | Feature |
|---|---|
| Phase 5 | Resume upload + resume-based interviews |
| Phase 6 | Situational interview mode |
| Phase 7 | Pronunciation analysis (real audio scoring) |
| Phase 8 | Debate & discussion mode |
| Phase 9 | Vocabulary training with spaced repetition |
| Phase 10 | Analytics dashboard + admin panel |
| Phase 11 | Mobile app |

---

## Workflow Rules for Agents (AI & Human)

1. **Always check which phase you are in** before writing code.
2. **Do not build Phase N+1 features** while Phase N is incomplete.
3. **If a feature is listed as Extra/Post-MVP** in `04_MVP_vs_EXTRA.md`, skip it.
4. **If unsure**, check `07_GUARDRAILS.md` for decision rules.
5. **Mark tasks as done** `[x]` in this file as you complete them.


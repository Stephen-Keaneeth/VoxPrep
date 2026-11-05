# VOXPREP — Phase Acceptance Criteria

> ⛔ **HARD RULE:** A phase is NOT complete until ALL criteria in that phase are met.  
> Do not move to the next phase until every checkbox below is ticked.

---

## Phase 0 — Project Setup

**Must pass ALL of these:**

- [ ] Git repository created and both members have push access
- [ ] `frontend/` directory initialized — `npm run dev` works with no errors
- [ ] `backend/` directory initialized — `uvicorn app.main:app` works with no errors
- [ ] Supabase project created with these tables: `users`, `interview_sessions`, `coach_sessions`
- [ ] `.env` files exist (not committed to git) with all required keys
- [ ] `GET /health` returns `{ "status": "ok" }` from backend
- [ ] Both members can access the Supabase dashboard
- [ ] Folder structure matches `02_TECH_STACK.md`

**✅ Phase 0 PASS → Proceed to Phase 1**

---

## Phase 1 — Foundation & Voice Pipeline

**Must pass ALL of these:**

- [ ] User can register a new account (email + password)
- [ ] User can log in and is redirected to the dashboard
- [ ] `POST /voice/process` accepts an audio file/blob and returns a text response
- [ ] LLM client (`llm.py`) successfully calls Gemini API and returns a coherent response
- [ ] STT converts a recorded audio clip to accurate text (test with a 5-word sentence)
- [ ] TTS converts a short text string to playable audio in the browser
- [ ] End-to-end voice loop works: speak → STT → LLM → TTS → hear response
- [ ] `VoiceRecorder.tsx` captures mic input and sends to backend
- [ ] `VoicePlayer.tsx` plays back audio response from backend
- [ ] Landing page renders with both CTAs functional (links to correct routes)
- [ ] No unhandled console errors on the frontend

**✅ Phase 1 PASS → Proceed to Phase 2**

---

## Phase 2 — Agent 1: AI Interviewer

**Must pass ALL of these:**

- [ ] User can configure an interview: select type (HR or Technical), enter role and experience level
- [ ] Interview session starts with Agent 1 introducing itself via voice
- [ ] Agent 1 asks exactly one question at a time — does NOT ask the next question until the previous answer is received
- [ ] After each answer, Agent 1 either asks a relevant follow-up OR moves to the next question
- [ ] Agent 1 does NOT reveal answers before the user responds
- [ ] Agent 1 does NOT repeat the same question
- [ ] Interview ends cleanly after a fixed number of questions (5 for MVP) or when user clicks "End Interview"
- [ ] Session data (questions, answers, timestamps) is saved to Supabase `interview_sessions`
- [ ] Report generates after interview ends
- [ ] Report contains: overall score, per-dimension scores, strengths, weaknesses, improvement tips
- [ ] Report page renders correctly and is readable
- [ ] "Go to Coach" button on the report page navigates to coach setup

**✅ Phase 2 PASS → Proceed to Phase 3**

---

## Phase 3 — Agent 2: AI Communication Coach

**Must pass ALL of these:**

- [ ] User can select a coach mode: Conversation Practice, Answer Training, or English Improvement
- [ ] Coach session starts with the AI Coach greeting the user and explaining the mode
- [ ] Coach speaks/poses a prompt to the user via voice
- [ ] User can respond via voice
- [ ] Coach provides a correction or improvement after each user response — politely worded
- [ ] Coach shows the improved sentence alternative on screen
- [ ] Coach does NOT interrupt mid-sentence
- [ ] Coach does NOT make the user feel embarrassed (no harsh language)
- [ ] Session data is saved to Supabase `coach_sessions`
- [ ] User's communication profile updates after session ends (skill level and weak areas)
- [ ] Dashboard shows updated communication profile

**✅ Phase 3 PASS → Proceed to Phase 4**

---

## Phase 4 — Polish & Deployment

**Must pass ALL of these:**

- [ ] Dashboard shows list of past interview sessions (date, type, overall score)
- [ ] Dashboard shows list of past coach sessions (date, mode)
- [ ] Dashboard shows communication profile (skill level, weak areas, strong areas)
- [ ] All pages have loading states (spinner or skeleton) while API calls are in progress
- [ ] All pages have error states (friendly message if something fails)
- [ ] Mobile layout is usable on a 375px wide screen (basic check)
- [ ] Frontend deployed to Vercel — production URL works
- [ ] Backend deployed to Railway — production URL works
- [ ] All environment variables are set in Vercel and Railway dashboards
- [ ] Full end-to-end flow works on production: Register → Interview → Report → Coach → Dashboard
- [ ] `README.md` written with: project description, setup steps, environment variables list, how to run

**✅ Phase 4 PASS → MVP IS COMPLETE 🎉**

---

## Failure Protocol

If a phase fails acceptance criteria:

1. **Do NOT proceed** to the next phase.
2. **Identify** which specific criteria are failing.
3. **Fix only** those criteria — do not refactor unrelated code.
4. **Re-check** all criteria for the current phase.
5. **Then proceed** when all pass.


# VOXPREP — Two-Member Task Division

> 👤 **Member A** = Backend / AI / LLM focus  
> 👤 **Member B** = Frontend / UI / Voice UX focus  
> Both members must sync at every **phase gate** before proceeding.

---

## Sync Points (Critical)

| When | What to sync on |
|---|---|
| After Phase 0 | Confirm API endpoints and data models match |
| After Phase 1 | Test voice loop together end-to-end |
| After Phase 2 | Test full interview session together |
| After Phase 3 | Test coach session together |
| After Phase 4 | Do final smoke test on production together |

---

## Phase 0 — Setup (Both, ~15 min each)

| Task | Member A | Member B |
|---|---|---|
| Create GitHub repo, invite both | ✅ Lead | Accepts invite |
| Set up backend (`FastAPI`) | ✅ | |
| Set up frontend (`Next.js`) | | ✅ Lead |
| Create Supabase project + tables | ✅ | |
| Share API keys / `.env` values securely | ✅ Shares | ✅ Receives |
| Confirm both environments run locally | ✅ | ✅ |

---

## Phase 1 — Foundation & Voice Pipeline

| Task | Member A | Member B |
|---|---|---|
| `llm.py` — Gemini API wrapper | ✅ | |
| `stt.py` — Speech-to-Text client | ✅ | |
| `tts.py` — Text-to-Speech client | ✅ | |
| `POST /voice/process` endpoint | ✅ | |
| Auth endpoints (`/auth/register`, `/auth/login`) | ✅ | |
| Landing page design + CTAs | | ✅ |
| Login + Register pages | | ✅ |
| `VoiceRecorder.tsx` | | ✅ |
| `VoicePlayer.tsx` | | ✅ |
| `VoiceVisualizer.tsx` (animated waveform) | | ✅ |
| Wire frontend voice → backend endpoint | ✅ (backend side) | ✅ (frontend side) |

---

## Phase 2 — Agent 1: AI Interviewer

| Task | Member A | Member B |
|---|---|---|
| `agents/interviewer.py` — full session logic | ✅ | |
| Interview system prompt (HR + Technical) | ✅ | |
| Answer evaluation rubric logic | ✅ | |
| `services/report.py` — report generator | ✅ | |
| `routers/interview.py` — all endpoints | ✅ | |
| Save session to Supabase | ✅ | |
| `/interview/setup` page | | ✅ |
| `/interview/session` page — full voice UI | | ✅ |
| `/interview/report` page — render report | | ✅ |
| Connect session page to backend endpoints | ✅ (API contract) | ✅ (API calls) |

---

## Phase 3 — Agent 2: AI Communication Coach

| Task | Member A | Member B |
|---|---|---|
| `agents/coach.py` — full session logic | ✅ | |
| Coach system prompt (3 modes) | ✅ | |
| Communication profile update logic | ✅ | |
| `routers/coach.py` — all endpoints | ✅ | |
| Save coach session to Supabase | ✅ | |
| `/coach/setup` page — mode selection | | ✅ |
| `/coach/session` page — voice + correction UI | | ✅ |
| Correction panel component | | ✅ |
| Connect coach session to backend | ✅ (API contract) | ✅ (API calls) |

---

## Phase 4 — Polish & Deployment

| Task | Member A | Member B |
|---|---|---|
| Deploy backend to Railway | ✅ | |
| Set Railway environment variables | ✅ | |
| Deploy frontend to Vercel | | ✅ |
| Set Vercel environment variables | | ✅ |
| Dashboard — past sessions list | | ✅ |
| Dashboard — communication profile display | | ✅ |
| Loading states on all pages | | ✅ |
| Error handling on all pages | Shared | Shared |
| Final smoke test (production) | ✅ | ✅ |
| Write `README.md` | ✅ (backend section) | ✅ (frontend section) |

---

## Communication Protocol

- **Stuck for > 20 min?** → Tell the other member immediately. Do not silently block.
- **API contract changes** → Member A must inform Member B before changing any endpoint shape.
- **Scope questions** → Check `04_MVP_vs_EXTRA.md` first. If still unsure, decide together.
- **Phase complete?** → Both members run through `05_ACCEPTANCE_CRITERIA.md` together before saying "done".

---

## Shared Responsibilities

Both members are responsible for:
- Keeping `docs/` files updated when anything changes
- Not merging code that breaks the main branch
- Testing their own code before marking a task complete


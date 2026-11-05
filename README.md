# VOXPREP 🎙️
### AI-Powered Voice Interview & Communication Coach Platform

> **Theme:** Voice AI | **MVP Sprint:** 8–12 hours | **Team:** 2 members

---

## What is VOXPREP?

VOXPREP is a voice-first AI platform that helps students and job seekers:
- Practice realistic mock interviews with an AI interviewer
- Improve communication skills with an AI coach
- Get personalized, data-driven feedback and performance reports

---

## Two Core AI Agents

| Agent | Role |
|---|---|
| 🎯 **Agent 1 — AI Interviewer** | Conducts realistic HR and Technical interviews. Evaluates answers. Generates performance reports. |
| 🗣 **Agent 2 — AI Communication Coach** | Provides conversational English practice, answer training, grammar correction, and vocabulary improvement. |

---

## Quick Start (Development)

### Prerequisites
- Node.js 18+
- Python 3.11+
- Supabase account
- NVIDIA Nemotron API key OR Google Gemini API key

### Frontend Setup
```bash
cd frontend
npm install
cp .env.local.example .env.local
# Fill in your Supabase keys in .env.local
npm run dev
```

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in your Gemini API key and Supabase keys in .env
uvicorn app.main:app --reload
```

---

## Environment Variables

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (`backend/.env`)
```
NVIDIA_API_KEY=nvapi-your_nvidia_api_key_here
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
```

> 💡 Get your free NVIDIA API key (no credit card) at https://build.nvidia.com  
> ~1000 credits on signup — easily covers a full 8–12 hour hackathon build.

---

## Project Documentation

All planning and architecture documents are in the `docs/` folder:

| File | Contents |
|---|---|
| [`00_PROJECT_OVERVIEW.md`](docs/00_PROJECT_OVERVIEW.md) | High-level summary and document index |
| [`01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) | System architecture and flow diagrams |
| [`02_TECH_STACK.md`](docs/02_TECH_STACK.md) | Technology choices and project structure |
| [`03_PHASE_PLAN.md`](docs/03_PHASE_PLAN.md) | Phase-by-phase build plan with task lists |
| [`04_MVP_vs_EXTRA.md`](docs/04_MVP_vs_EXTRA.md) | MVP feature list and what's deferred |
| [`05_ACCEPTANCE_CRITERIA.md`](docs/05_ACCEPTANCE_CRITERIA.md) | Per-phase pass/fail gates |
| [`06_TASK_DIVISION.md`](docs/06_TASK_DIVISION.md) | Member A and Member B responsibilities |
| [`07_GUARDRAILS.md`](docs/07_GUARDRAILS.md) | Do's, Don'ts, Fallbacks, Agent rules |
| [`08_AGENT_PROMPTS.md`](docs/08_AGENT_PROMPTS.md) | System prompts for Agent 1 and Agent 2 |

---

## Build Phases

```
Phase 0 (Setup)       ~30 min
Phase 1 (Voice Loop)  ~1.5 hrs
Phase 2 (Interviewer) ~3 hrs
Phase 3 (Coach)       ~2.5 hrs
Phase 4 (Deploy)      ~1 hr
─────────────────────────────
Total MVP:            ~8.5 hrs
```

---

## Tech Stack

- **Frontend:** Next.js 14, Tailwind CSS, shadcn/ui, Zustand
- **Backend:** FastAPI (Python)
- **LLM:** NVIDIA Nemotron 70B (`nvidia/llama-3.1-nemotron-70b-instruct`) via NVIDIA NIM
- **STT:** NVIDIA Nemotron ASR / Parakeet via NVIDIA NIM REST API
- **TTS:** NVIDIA Magpie TTS via NVIDIA NIM / Web Speech API (fallback)
- **AI Provider:** NVIDIA API Catalog — single `NVIDIA_API_KEY` (~1000 free credits, hackathon-safe)
- **Database & Auth:** Supabase (PostgreSQL) — free tier
- **Deployment:** Vercel (frontend) + Railway (backend) — free tiers

---

## Contributing (Team Rules)

1. Work in phases — do not build Phase N+1 until Phase N passes acceptance criteria.
2. Check `07_GUARDRAILS.md` before adding any new feature.
3. Check `04_MVP_vs_EXTRA.md` before starting any task — if it's not MVP, skip it.
4. Keep secrets out of the repository.
5. Communicate when blocked — don't stay stuck for more than 20 minutes silently.


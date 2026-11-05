# VOXPREP — Approved Technology Stack

> ⚠️ **LOCKED FOR MVP** — Do not change any technology without updating this file and getting team approval.

---

## Stack Decision Table

| Layer | Technology | Reason | MVP? |
|---|---|---|---|
| **Frontend Framework** | Next.js 14 (App Router) | Fast setup, SSR, easy deployment | ✅ MVP |
| **UI Library** | Tailwind CSS + shadcn/ui | Rapid UI development | ✅ MVP |
| **Voice Capture** | Browser MediaRecorder API | No extra dependency, works in browser | ✅ MVP |
| **Speech-to-Text (STT)** | Gemini Live API (primary) / Deepgram (fallback) | Accurate, low latency | ✅ MVP |
| **LLM** | Google Gemini 2.0 Flash | Fast, cost-effective, long context | ✅ MVP |
| **Text-to-Speech (TTS)** | Web Speech API (primary) / ElevenLabs (fallback) | Zero-cost for MVP | ✅ MVP |
| **Backend Framework** | FastAPI (Python) | Async support, easy LLM integration | ✅ MVP |
| **Database** | Supabase (PostgreSQL) | Auth + DB in one, free tier | ✅ MVP |
| **Auth** | Supabase Auth | Built into Supabase, quick setup | ✅ MVP |
| **Deployment** | Vercel (Frontend) + Railway (Backend) | Free tiers, fast deploy | ✅ MVP |
| **State Management** | Zustand (Frontend) | Lightweight | ✅ MVP |
| **API Communication** | REST (HTTP) + WebSocket (voice stream) | Standard + real-time needs | ✅ MVP |
| **Environment Config** | `.env.local` (Next.js) + `.env` (FastAPI) | Standard secret management | ✅ MVP |

---

## Extra / Post-MVP Technologies

| Technology | Purpose | Phase |
|---|---|---|
| Deepgram Streaming | Real-time streaming STT | Post-MVP |
| ElevenLabs | Premium voice synthesis | Post-MVP |
| Redis | Session caching, rate limiting | Post-MVP |
| LangGraph / LangChain | Complex agent orchestration | Post-MVP |
| Pinecone / pgvector | Vector search for question retrieval | Post-MVP |
| Analytics Dashboard | Usage tracking | Post-MVP |
| Mobile App (React Native) | Mobile support | Future |

---

## API Keys Required

| Service | Key Name | Where to Set |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | `.env` (backend) |
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `.env.local` (frontend) + `.env` (backend) |
| Deepgram (optional fallback) | `DEEPGRAM_API_KEY` | `.env` (backend) |
| ElevenLabs (optional fallback) | `ELEVENLABS_API_KEY` | `.env` (backend) |

---

## Project Structure

```
AI-Interviewer/
├── docs/                        ← All .md project docs live here
│   ├── 00_PROJECT_OVERVIEW.md
│   ├── 01_ARCHITECTURE.md
│   ├── 02_TECH_STACK.md
│   ├── 03_PHASE_PLAN.md
│   ├── 04_MVP_vs_EXTRA.md
│   ├── 05_ACCEPTANCE_CRITERIA.md
│   ├── 06_TASK_DIVISION.md
│   ├── 07_GUARDRAILS.md
│   └── 08_AGENT_PROMPTS.md
│
├── frontend/                    ← Next.js app
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── dashboard/
│   │   ├── interview/
│   │   │   ├── setup/
│   │   │   ├── session/
│   │   │   └── report/
│   │   ├── coach/
│   │   │   ├── setup/
│   │   │   └── session/
│   │   └── layout.tsx
│   ├── components/
│   │   ├── voice/
│   │   │   ├── VoiceRecorder.tsx
│   │   │   ├── VoicePlayer.tsx
│   │   │   └── VoiceVisualizer.tsx
│   │   ├── interview/
│   │   ├── coach/
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts
│   │   ├── supabase.ts
│   │   └── voice.ts
│   ├── store/
│   │   └── session.ts
│   └── .env.local
│
├── backend/                     ← FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── interview.py
│   │   │   ├── coach.py
│   │   │   └── voice.py
│   │   ├── agents/
│   │   │   ├── interviewer.py
│   │   │   └── coach.py
│   │   ├── services/
│   │   │   ├── llm.py
│   │   │   ├── stt.py
│   │   │   ├── tts.py
│   │   │   └── report.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   └── report.py
│   │   └── db/
│   │       └── supabase.py
│   ├── requirements.txt
│   └── .env
│
└── README.md
```


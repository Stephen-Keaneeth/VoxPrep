# VOXPREP — Approved Technology Stack

> ⚠️ **LOCKED FOR MVP** — Do not change any technology without updating this file and getting team approval.

> 🟢 **AI Stack:** This project uses **NVIDIA Nemotron** as the unified AI provider for LLM, STT, and TTS — single `NVIDIA_API_KEY`, designed for hackathon-scale prototyping. Credits last well beyond 8–12 hours of active usage.

---

## Stack Decision Table

| Layer | Technology | Reason | MVP? | Cost |
|---|---|---|---|---|
| **Frontend Framework** | Next.js 14 (App Router) | Fast setup, SSR, easy deployment | ✅ MVP | Free |
| **UI Library** | Tailwind CSS + shadcn/ui | Rapid UI development | ✅ MVP | Free |
| **Voice Capture** | Browser MediaRecorder API | No extra dependency, works in browser | ✅ MVP | Free — browser built-in |
| **Speech-to-Text (STT)** | NVIDIA Nemotron ASR / Parakeet via NVIDIA NIM REST API | Same API key, accurate, hackathon credits cover full build | ✅ MVP | Free credits (hackathon-safe) |
| **LLM** | NVIDIA Nemotron (`nvidia/llama-3.1-nemotron-70b-instruct`) | OpenAI-compatible, agentic reasoning, function calling | ✅ MVP | Free credits (hackathon-safe) |
| **Text-to-Speech (TTS)** | NVIDIA Magpie TTS via NVIDIA NIM / Web Speech API (fallback) | Natural voice, multilingual; fallback if credits low | ✅ MVP | Free credits / browser fallback |
| **Backend Framework** | FastAPI (Python) | Async support, easy LLM integration | ✅ MVP | Free |
| **Database** | Supabase (PostgreSQL) | Auth + DB in one, free tier (500MB, 2 projects) | ✅ MVP | Free tier |
| **Auth** | Supabase Auth | Built into Supabase, quick setup | ✅ MVP | Free tier |
| **Deployment** | Vercel (Frontend) + Railway (Backend) | Free tiers, fast deploy | ✅ MVP | Free tier |
| **State Management** | Zustand (Frontend) | Lightweight | ✅ MVP | Free |
| **API Communication** | REST (HTTP) + WebSocket (voice stream) | Standard + real-time needs | ✅ MVP | Free |
| **Environment Config** | `.env.local` (Next.js) + `.env` (FastAPI) | Standard secret management | ✅ MVP | Free |

---

## Extra / Post-MVP Technologies

> These may involve paid APIs — evaluate cost before adding.

| Technology | Purpose | Phase |
|---|---|---|
| NVIDIA Nemotron VoiceChat (Speech-to-Speech) | Full-duplex end-to-end voice (no STT→LLM→TTS hops) | Post-MVP |
| NVIDIA Nemotron ASR Streaming (gRPC) | Real-time low-latency streaming STT | Post-MVP |
| NVIDIA Magpie TTS Zeroshot | Zero-shot voice cloning for custom interviewer voice | Post-MVP |
| Redis | Session caching, rate limiting | Post-MVP |
| LangGraph / LangChain | Complex agent orchestration | Post-MVP |
| Pinecone / pgvector | Vector search for question retrieval | Post-MVP |
| Analytics Dashboard | Usage tracking | Post-MVP |
| Mobile App (React Native) | Mobile support | Future |

---

## API Keys Required

| Service | Key Name | Where to Set | Notes |
|---|---|---|---|
| **NVIDIA NIM** | `NVIDIA_API_KEY` | `.env` (backend) | Covers LLM + STT + TTS. ~1000 free credits on signup — sufficient for full hackathon |
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `.env.local` (frontend) + `.env` (backend) | Free tier |
| Web Speech API (TTS fallback) | — | None (browser built-in) | Free, no key needed |

> 💡 Get your NVIDIA API key (no credit card) at: https://build.nvidia.com → Sign in → Get API Key  
> 💡 **Credit tip:** To conserve credits during development, use short test prompts. Run full sessions only during integration testing and final demo.

### NVIDIA NIM Endpoints Used

| Capability | Model | Base URL |
|---|---|---|
| LLM | `nvidia/llama-3.1-nemotron-70b-instruct` | `https://integrate.api.nvidia.com/v1` |
| STT | `nvidia/parakeet-ctc-1.1b-asr` | `https://integrate.api.nvidia.com/v1` |
| TTS | `nvidia/magpie-tts-multilingual` | `https://integrate.api.nvidia.com/v1` |

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


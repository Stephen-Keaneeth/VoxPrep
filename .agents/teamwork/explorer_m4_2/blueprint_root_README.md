# VOXPREP 🎙️⚡
### AI-Powered Voice Interview & Communication Coaching Platform

> **Theme:** Voice AI | **Sprint Scope:** 8–12 Hour MVP | **Target Platform:** Web (Next.js + FastAPI)  
> **Backend AI Provider:** NVIDIA NIM (Nemotron 70B LLM, Parakeet STT, Magpie TTS) | **Database & Auth:** Supabase

---

## 🌟 What is VOXPREP?

**VOXPREP** is an adaptive, voice-first platform engineered to help job seekers and students excel in competitive technical interviews and daily professional communication. 

Unlike static quiz generators or text-only chatbots, VOXPREP delivers **natural voice-to-voice dialogues**, real-time rubric-based evaluation, and adaptive communication coaching powered by two dedicated AI agents.

---

## 🤖 The Two Core AI Agents

| Agent | Name | Role & Capabilities |
|---|---|---|
| 🎯 **Agent 1** | **AI Interviewer** | • Conducts realistic **HR & Technical** mock interviews.<br>• Evaluates answers in real time across **4 dimensions**: Relevance, Clarity, Depth, Examples (1–10 scale).<br>• Asks contextually adaptive follow-ups (max 1 follow-up/question, max 5 questions/session).<br>• Generates comprehensive performance reports with actionable improvement steps. |
| 🗣 **Agent 2** | **AI Communication Coach** | • 3 practice modes: **Everyday Conversation**, **Answer Training**, and **English Improvement**.<br>• Delivers polite, constructive corrections (max 1–2 per exchange) with clearer alternatives.<br>• Tracks persistent communication profile: adapts to `skill_level`, `weak_areas`, and `strong_areas`. |

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        VOXPREP PLATFORM                                │
│                                                                        │
│   ┌───────────────────────────┐      Voice Audio / REST JSON           │
│   │   Frontend (Next.js 14)   │◄───────────────────────────────────┐   │
│   │   • VoiceRecorder (WAV)   │                                    │   │
│   │   • VoiceVisualizer       │                                    │   │
│   │   • Interview & Coach UIs │                                    │   │
│   └─────────────┬─────────────┘                                    │   │
│                 │                                                  │   │
│                 ▼                                                  │   │
│   ┌─────────────────────────────────────────────────────────────┐  │   │
│   │                 Backend (FastAPI on Railway)                │  │   │
│   │                                                             │  │   │
│   │   ┌───────────────────────┐     ┌────────────────────────┐  │  │   │
│   │   │ AGENT 1: Interviewer  │     │ AGENT 2: Coach         │  │  │   │
│   │   │ • Question Generation │     │ • Exercise Engine      │  │  │   │
│   │   │ • 4-Dimension Rubric  │     │ • 1-2 Corrections Max  │  │  │   │
│   │   │ • Report Generator    │     │ • Profile Learning     │  │  │   │
│   │   └──────────┬────────────┘     └───────────┬────────────┘  │  │   │
│   │              └──────────────┬───────────────┘               │  │   │
│   │                             ▼                               │  │   │
│   │               ┌───────────────────────────┐                 │  │   │
│   │               │   Shared AI & DB Engine   │                 │  │   │
│   │               │   • NVIDIA Nemotron 70B   │                 │  │   │
│   │               │   • NVIDIA Parakeet ASR   │                 │  │   │
│   │               │   • NVIDIA Magpie TTS     │                 │  │   │
│   │               │   • Supabase Auth & DB    │                 │  │   │
│   │               └─────────────┬─────────────┘                 │  │   │
│   └─────────────────────────────┼───────────────────────────────┘  │   │
│                                 │                                  │   │
│                                 └──────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 👥 Two-Member Team Division

VOXPREP is divided cleanly between Member A (Backend / AI) and Member B (Frontend / UX) per [`docs/06_TASK_DIVISION.md`](docs/06_TASK_DIVISION.md):

- **Member A (Backend Lead)**: FastAPI, NVIDIA NIM voice pipeline, Interview & Coach agent state machines, Supabase persistence, global error middleware, automated test suite, Docker containerization & Railway deployment.
- **Member B (Frontend Lead)**: Next.js 14 App Router, Tailwind CSS, shadcn/ui, audio recording via browser MediaRecorder, voice visualizer, session management UI, and API integration with backend contracts.

---

## ⚡ Quick Start (Local Development)

### 1. Prerequisites
- **Node.js**: v18.0+ & npm
- **Python**: 3.11+ or 3.12 (Python 3.12 recommended)
- **NVIDIA NIM API Key**: Free at [build.nvidia.com](https://build.nvidia.com) (~1000 credits on signup, no credit card required)
- **Supabase Account**: Free project at [supabase.com](https://supabase.com)

---

### 2. Backend Setup (FastAPI)

#### Step 2.1: Dedicated Python Virtual Environment (`.venv`)
Always use a dedicated virtual environment to prevent package version conflicts:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(If script execution is disabled in PowerShell, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 2.2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

#### Step 2.3: Configure Environment Variables
```bash
cp backend/.env.example backend/.env
```
Fill in your credentials in `backend/.env`:
```ini
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# NVIDIA NIM (Single key covers LLM, STT, and TTS)
NVIDIA_API_KEY=nvapi-your_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# Supabase Project Credentials
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
```

#### Step 2.4: Initialize Database Tables
Execute the idempotent SQL script `backend/schema.sql` in the **SQL Editor** of your Supabase Dashboard.

#### Step 2.5: Start Backend Server
```bash
# From project root:
uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000
```
- API Root: [http://localhost:8000/](http://localhost:8000/)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)
- Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Step 2.6: Run Backend Automated Tests
```bash
pytest backend/tests -v
```

---

### 3. Frontend Setup (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

Configure `frontend/.env.local`:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

Run the development server:
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📡 API Contract Reference for Member B (Frontend)

Below is the summary of backend endpoints. All endpoints return consistent JSON error envelopes on failure (400, 401, 404, 422, 500).

| Method | Endpoint | Description | Request Payload / Format |
|---|---|---|---|
| `GET` | `/health` | Service uptime healthcheck | None |
| `GET` | `/` | API status and doc links | None |
| `POST` | `/auth/register` | Register user & initialize profile | `{"email": str, "password": str, "name"?: str}` |
| `POST` | `/auth/login` | Login user & retrieve access token | `{"email": str, "password": str}` |
| `POST` | `/voice/process` | End-to-end voice loop (STT -> LLM -> TTS) | `multipart/form-data`: `file` (WAV audio), `agent_type?`, `session_id?` |
| `POST` | `/interview/start` | Start mock interview session | `{"candidate_name": str, "role": str, "experience_level": str, "interview_type": "hr" \| "technical"}` |
| `POST` | `/interview/respond`| Submit candidate answer | `{"session_id": str, "answer_text": str}` |
| `POST` | `/interview/end` | Finalize interview & generate report | `{"session_id": str}` |
| `GET` | `/interview/report/{id}` | Retrieve performance report | Path parameter: `session_id` |
| `POST` | `/coach/start` | Start communication coaching session | `{"user_id": str, "mode": "conversation" \| "answer_training" \| "english_improvement"}` |
| `POST` | `/coach/respond` | Submit speech to coach & get 1-2 corrections | `{"session_id": str, "user_text": str}` |
| `POST` | `/coach/end` | Conclude session & update user profile | `{"session_id": str}` |

> 📘 **Exhaustive Contract Documentation**:  
> For complete request/response schemas, sample responses, and cURL commands, consult:
> - Detailed Integration Guide: [`.agents/teamwork/explorer_m4_2/api_contract_reference.md`](.agents/teamwork/explorer_m4_2/api_contract_reference.md)
> - Dedicated Backend README: [`backend/README.md`](backend/README.md)

---

## 🛡️ Guardrails & Conversational Boundaries

- **Single Follow-Up**: Interviewer asks at most **1 follow-up** per core question.
- **Session Boundary**: Mock interviews conclude after **5 core questions**.
- **Coach Corrections**: Coach provides at most **1–2 constructive corrections** per exchange.
- **Graceful Fallbacks**:
  * Unintelligible audio -> Prompt user to repeat without crashing.
  * TTS service unavailable -> `audio_base64: null` allows immediate frontend Web Speech API fallback.
  * Missing API keys -> Safe in-memory mock fallback mode for offline testing.

---

## 🚢 Production Deployment

- **Backend**: Containerized via `Dockerfile` and configured with `railway.json` for one-click deployment on [Railway](https://railway.app).
- **Frontend**: Configured for continuous deployment on [Vercel](https://vercel.com).

---

## 📚 Project Documentation Index

All architectural specs and design decisions are cataloged in `docs/`:

| Doc | Subject |
|---|---|
| [`00_PROJECT_OVERVIEW.md`](docs/00_PROJECT_OVERVIEW.md) | Vision, Problem Statement & Doc Index |
| [`01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) | System Flow & Component Diagrams |
| [`02_TECH_STACK.md`](docs/02_TECH_STACK.md) | Approved Tech Stack & NVIDIA NIM Endpoints |
| [`03_PHASE_PLAN.md`](docs/03_PHASE_PLAN.md) | Milestones 0 to 4 Sprint Roadmap |
| [`04_MVP_vs_EXTRA.md`](docs/04_MVP_vs_EXTRA.md) | Scope Boundaries & Post-MVP Backlog |
| [`05_ACCEPTANCE_CRITERIA.md`](docs/05_ACCEPTANCE_CRITERIA.md) | Quality Gates & Pass/Fail Criteria |
| [`06_TASK_DIVISION.md`](docs/06_TASK_DIVISION.md) | Member A & B Ownership Matrix |
| [`07_GUARDRAILS.md`](docs/07_GUARDRAILS.md) | Error Handling, Agent Constraints & Tone Rules |
| [`08_AGENT_PROMPTS.md`](docs/08_AGENT_PROMPTS.md) | Prompt Engineering for Interviewer & Coach |

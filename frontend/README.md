# VOXPREP — Frontend Architecture & Client Integration Guide

Minimal, elegant, voice-first AI platform for video mock interviews and communication coaching.

---

## 1. Tech Stack & Core Dependencies
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5.6 (Strict typing across all data layers)
- **Styling**: Tailwind CSS with custom design system tokens (`DESIGN.md` — Navy `#0B1120`, `#111A2E`, `#2563EB`, `#F8FAFC`)
- **State Management**: Zustand (`frontend/store/useStore.ts`)
- **Database & Persistence**: Supabase JS (`@supabase/supabase-js` v2) aligned 100% with `backend/schema.sql`
- **Voice Pipeline**: WebRTC MediaStreams, Web Audio API `AnalyserNode`, `MediaRecorder`, and native Web Speech API fallback

---

## 2. Five Main Sections
1. **Home Dashboard** (`components/sections/HomeDashboard.tsx`): Candidate readiness overview, dynamic average scores, WPM, and unified recent mock sessions table with direct links to performance reports.
2. **AI Interview Agent** (`components/sections/InterviewAgent.tsx`): Call-based video interface with active camera feed (`getUserMedia`), AI interviewer presence, live closed captions, call controls (Mute, Camera toggle, CC, End Call), and adaptive resume question tailoring.
3. **AI Communication Coach** (`components/sections/CommunicationAgent.tsx`): Real-time speaking practice, 3 coaching modes (STAR Structuring, Everyday Fluency, Executive Vocabulary), dynamic WPM pacing meter, and inline filler word tags.
4. **Interview Performance Dashboard** (`components/sections/InterviewDashboard.tsx`): 4-rubric evaluation (Relevance, Technical Depth, Answer Clarity, Structural Examples), strengths, and targeted growth areas.
5. **Communication Performance Dashboard** (`components/sections/CommunicationDashboard.tsx`): Vocal vitals (WPM, filler rate, grammar accuracy, fluency tier), and weekly trajectory tracking.

---

## 3. Backend Alignment (Member A Contracts)

### Authentication Endpoints (`backend/app/routers/auth.py`)
- `POST /auth/register`:
  - Request: `{ "email": string, "password": string, "name": string }`
  - Response: `{ "user": { "id": string, "email": string, "name": string }, "access_token": string }`
- `POST /auth/login`:
  - Request: `{ "email": string, "password": string }`
  - Response: `{ "user": { "id": string, "email": string, "name": string }, "access_token": string }`

### Voice Pipeline Endpoint (`backend/app/routers/voice.py`)
- `POST /voice/process` (Multipart / Form-Data):
  - `file`: Audio recording blob (WebM / WAV)
  - `agent_type`: `"interview"` | `"coach"`
  - `session_id`: Optional session UUID
  - `conversation_history`: Optional dialog context
  - Returns: `{ "transcript": string, "spoken_response": string, "audio_base64": string | null, "session_id": string }`

### Database Tables (`backend/schema.sql`)
- `interview_sessions`: Records mock interview questions, candidate answers, rubric scores, and report recommendations.
- `coach_sessions`: Records communication practice exchanges, WPM, detected fillers, and grammar feedback.
- `users`: Stores candidate identity and communication profiles.

---

## 4. Development & Build Scripts

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Run linting check
npm run lint

# Run optimized production build
npm run build

# Start production server
npm start
```


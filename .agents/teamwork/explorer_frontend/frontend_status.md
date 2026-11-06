# VoxPrep Frontend Codebase & Environment Status Report

**Date**: 2026-11-06  
**Agent**: teamwork_explorer (`explorer_frontend`)  
**Workspace**: `c:\Project\VoxPrep\frontend`  
**Parent Orchestrator ID**: `55e0bf3f-dbbe-407b-930a-d465c34fe1ef`

---

## 1. Executive Summary

The VoxPrep frontend is a Next.js 14 App Router application (`voxprep-frontend` v0.1.0) with Tailwind CSS, TypeScript, Zustand, and Lucide React.
The project **currently passes type checking (`npx tsc --noEmit`)**, **ESLint (`npm run lint`)**, and **production build (`npm run build`)** with zero errors.

However, an architectural audit against `ORIGINAL_REQUEST.md` and the FastAPI backend (`backend/app/main.py`, `routers/`, `schema.sql`) reveals critical contract misalignment, mocked state bloat, and unbacked features that must be addressed during the ground-up rebuild:
1. **Unbacked Features**: A Next.js API route (`app/api/parse-resume/route.ts`), resume upload modal, and `pdf-parse` library exist despite having no corresponding FastAPI backend endpoints or database schema columns.
2. **Direct Client Database Access**: `lib/supabase.ts` contains direct Supabase client initialization and in-memory mock database collections that duplicate or bypass FastAPI backend endpoints.
3. **Mocked Bloat in State**: `store/useStore.ts` contains hardcoded candidate profiles ("Anish"), preloaded fake resumes, and mock history arrays.
4. **Navigation Redundancy**: `app/page.tsx` uses a tab switcher based on `activeSection` (1–5) in addition to individual Next.js app routes (`/interview`, `/coach`, `/analytics/interview`, etc.).
5. **Contract Consistency**: While `lib/api.ts` implements methods for the 9 backend endpoints, several functions return hardcoded mock fallbacks rather than strictly typed network responses with proper error surfacing.

---

## 2. Package & Dependency Audit (`frontend/package.json`)

### Core Dependencies
| Dependency | Version | Purpose | Assessment |
|------------|---------|---------|------------|
| `next` | `14.2.15` | App Router Web Framework | Up to date, stable Next.js 14 release |
| `react` | `^18.3.1` | UI Library | React 18 LTS |
| `react-dom` | `^18.3.1` | DOM Renderer | Matches React 18 |
| `zustand` | `^4.5.5` | Application State Store | Already installed and functional |
| `lucide-react` | `^0.453.0` | UI Icons | Fully installed and used across components |
| `clsx` | `^2.1.1` | Classname concatenation | Used in `lib/utils.ts` |
| `tailwind-merge` | `^2.5.4` | Tailwind class deduplication | Used in `lib/utils.ts` |
| `@supabase/supabase-js` | `^2.109.0` | Direct Supabase Client | **Bloat/Gaps**: Frontend should communicate exclusively via FastAPI backend (`http://127.0.0.1:8000`) |
| `pdf-parse` | `^2.4.5` | PDF Resume Parsing | **Bloat/Gaps**: Not backed by FastAPI backend routes or database schema |
| `@types/pdf-parse` | `^1.1.5` | PDF Parse TypeScript types | Unnecessary if `pdf-parse` is removed |

### Dev Dependencies
| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| `typescript` | `^5.6.3` | Static Type Checker | Verified clean build with strict mode |
| `@types/node` | `^20.17.0` | Node typings | Compatible |
| `@types/react` | `^18.3.11` | React typings | Compatible |
| `@types/react-dom`| `^18.3.1` | ReactDOM typings | Compatible |
| `tailwindcss` | `^3.4.14` | Utility-first CSS | Fully configured with custom color palette |
| `postcss` | `^8.4.47` | CSS transformation | Configured |
| `autoprefixer` | `^10.4.20` | CSS vendor prefixing | Configured |
| `eslint` | `^8.57.0` | Linter | Configured |
| `eslint-config-next`| `^14.2.15` | Next.js lint rules | 0 warnings, 0 errors |

### Available Scripts
```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint"
}
```
*Recommendation*: Add `"tsc": "tsc --noEmit"` to `package.json` for rapid type verification.

---

## 3. Configuration & Styling Audit

### 3.1 TypeScript Configuration (`frontend/tsconfig.json`)
- Strict mode: `"strict": true`
- Module Resolution: `"bundler"`
- Target/Lib: `"dom", "dom.iterable", "esnext"`
- Path aliases: `"@/*": ["./*"]`
- NoEmit: `"noEmit": true`
- Status: **Verified**. `npx tsc --noEmit` exits with status 0 and 0 errors.

### 3.2 Tailwind Configuration (`frontend/tailwind.config.ts`)
- Configured color palette directly satisfies R5 requirement:
  - Canvas: `#0b1120` (Matches `#0B1120`)
  - Surface/Card: `#111a2e` (Matches `#111A2E`)
  - Brand Primary: `brand.600: #2563eb` (Matches `#2563EB`)
  - Accent / Hover: `card-hover: #16223b`, `navy: 950..500`, `brand: 500, 400`
  - Subtle Border: `borderColor.subtle = "rgba(255, 255, 255, 0.08)"`
- Content paths cover `./app/**/*.{js,ts,jsx,tsx,mdx}` and `./components/**/*.{js,ts,jsx,tsx,mdx}`.

### 3.3 Next.js Configuration (`frontend/next.config.mjs`)
- `reactStrictMode: true`
- Status: Clean build verified.

### 3.4 ESLint Configuration (`frontend/.eslintrc.json`)
- Extends `"next/core-web-vitals"`
- Status: `npm run lint` passes with 0 warnings or errors.

---

## 4. Current Frontend Directory Layout & File Structure

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx               # Login page calling POST /auth/login
│   │   └── register/page.tsx            # Register page calling POST /auth/register
│   ├── analytics/
│   │   ├── communication/page.tsx       # Communication report dashboard
│   │   └── interview/page.tsx           # Interview evaluation report dashboard
│   ├── api/
│   │   └── parse-resume/route.ts        # Next.js PDF parse route (OUT OF SCOPE / BLOAT)
│   ├── coach/page.tsx                   # Wrapper for CommunicationAgent
│   ├── dashboard/page.tsx               # Wrapper for HomeDashboard
│   ├── interview/page.tsx               # Wrapper for InterviewAgent
│   ├── globals.css                      # Global Tailwind & theme CSS
│   ├── layout.tsx                       # Root layout with Sidebar, Header, ToastContainer
│   └── page.tsx                         # Client-side tab router using activeSection 1..5
├── components/
│   ├── Header.tsx                       # App header with backend status checker
│   ├── Sidebar.tsx                      # App sidebar navigation
│   ├── interview/
│   │   ├── InterviewLobby.tsx           # Lobby & resume pre-check (OUT OF SCOPE / BLOAT)
│   │   └── ResumeUploadModal.tsx        # Resume upload modal (OUT OF SCOPE / BLOAT)
│   ├── sections/
│   │   ├── CommunicationAgent.tsx       # Coach room component
│   │   ├── CommunicationDashboard.tsx   # Communication report component
│   │   ├── HomeDashboard.tsx            # Readiness overview dashboard
│   │   ├── InterviewAgent.tsx           # Interview video room component
│   │   └── InterviewDashboard.tsx       # Interview report component
│   ├── ui/
│   │   └── ToastContainer.tsx           # Floating toast container
│   └── voice/
│       ├── VoicePlayer.tsx              # Audio playback with Web Speech fallback
│       ├── VoiceRecorder.tsx            # MediaRecorder audio capture
│       └── VoiceVisualizer.tsx          # Canvas audio visualizer
├── lib/
│   ├── api.ts                           # Client methods for backend endpoints
│   ├── resumeParser.ts                  # Client resume text parser (OUT OF SCOPE / BLOAT)
│   ├── supabase.ts                      # Client-side Supabase SDK & mock in-memory store
│   ├── utils.ts                         # Classnames (cn) helper
│   └── voice.ts                         # Web Speech API, WPM, and filler words utility
└── store/
    ├── useStore.ts                      # Zustand state store (contains mocked bloat)
    └── useToast.ts                      # Toast notification state store
```

---

## 5. Backend Alignment Audit (Single Source of Truth)

The backend provides the following 9 active endpoints:

| Endpoint | Method | Backend Handler | Request Model | Response Model |
|----------|--------|-----------------|---------------|----------------|
| `/health` | GET | `app.main.health_check` | *None* | `{"status": "ok"}` |
| `/auth/register` | POST | `app.routers.auth.register` | `RegisterRequest` | `AuthResponse` (`user`, `access_token`) |
| `/auth/login` | POST | `app.routers.auth.login` | `LoginRequest` | `AuthResponse` (`user`, `access_token`) |
| `/voice/process` | POST | `app.routers.voice.process_voice` | `file`, `agent_type`, `session_id`, `conversation_history` (Form) | `VoiceProcessResponse` (`transcript`, `spoken_response`, `audio_base64`, `session_id`) |
| `/interview/start` | POST | `app.routers.interview.start_interview` | `InterviewStartRequest` (`candidate_name`, `role`, `experience_level`, `interview_type`: `'hr'`\|`'technical'`, `user_id?`) | `InterviewStartResponse` (`session_id`, `opening_message`) |
| `/interview/respond` | POST | `app.routers.interview.respond_interview` | `InterviewRespondRequest` (`session_id`, `answer_text`) | `InterviewRespondResponse` (`spoken_response`, `is_complete`, `follow_up_or_next`, `question_index`, `current_question_index`, `total_questions`) |
| `/interview/end` | POST | `app.routers.interview.end_interview` | `InterviewEndRequest` (`session_id`) | `InterviewEndResponse` (`session_id`, `status`, `message`, `report`) |
| `/interview/report/{session_id}` | GET | `app.routers.interview.get_interview_report` | `session_id` (Path) | `InterviewReport` |
| `/coach/start` | POST | `app.routers.coach.start_coach` | `CoachStartRequest` (`user_id`, `mode`: `'conversation'`\|`'answer_training'`\|`'english_improvement'`) | `CoachStartResponse` (`session_id`, `opening_message`, `mode`) |
| `/coach/respond` | POST | `app.routers.coach.respond_coach` | `CoachRespondRequest` (`session_id`, `user_text`) | `CoachRespondResponse` (`coach_message`, `correction`, `next_prompt`) |
| `/coach/end` | POST | `app.routers.coach.end_coach` | `CoachEndRequest` (`session_id`) | `CoachEndResponse` (`session_id`, `status`, `summary`, `profile_updated`) |

### Critical Gaps Identified
1. **Resume Processing is Unbacked**:
   - `backend/app/main.py` and `backend/schema.sql` contain NO endpoints or tables for resume parsing, resume storage, or PDF ingestion.
   - `app/api/parse-resume/route.ts`, `lib/resumeParser.ts`, `components/interview/ResumeUploadModal.tsx`, and `components/interview/InterviewLobby.tsx` violate Requirement R1 ("Build ONLY what the backend requires and defines—no extra dummy features").
2. **Client-Side Supabase Bypassing Backend**:
   - `lib/supabase.ts` invokes `@supabase/supabase-js` directly and holds in-memory caches.
   - Per R1 and R2, the Next.js frontend must consume only the FastAPI backend REST API. The backend interacts with database persistence internally.
3. **Mocked Bloat in Zustand**:
   - `store/useStore.ts` contains hardcoded candidate profile, fake parsed resume questions, and pre-baked evaluation history.
   - Per R2: Store must manage *only* live authenticated user sessions, active session IDs, and fetched report payloads.
4. **Interaction Room Flow**:
   - `/interview` currently requires navigating past an `InterviewLobby` with resume tabs before entering call. It must instead directly initialize the camera preview and auto-start or offer one-click start calling `POST /interview/start`.
   - `/coach` mode selector uses custom internal strings (`star`, `fluency`, `vocab`) mapped to backend modes; it should directly use the exact 3 backend modes (`conversation`, `answer_training`, `english_improvement`).
5. **Score Normalization**:
   - Backend reports scale scores from 1.0 to 10.0 (e.g. `relevance`, `clarity`, `depth`, `examples`, `overall_score`).
   - Normalization formula `score <= 10 ? Math.round(score * 10) : score` must be uniformly applied across `/analytics/interview` and `/analytics/communication`.

---

## 6. Sub-Agent Work Breakdown Proposal

To execute the rebuild systematically per the specification:

1. **Agent A: API Client & State Architect**
   - Refactor `frontend/lib/api.ts` with strict TypeScript types mapping 1:1 to FastAPI Pydantic models.
   - Provide clean, typed client methods for all 9 backend endpoints with proper HTTP error handling.
   - Refactor `frontend/store/useStore.ts` into a minimal Zustand store: user session (id, email, name, token), active session IDs (`interviewSessionId`, `coachSessionId`), and cached report payloads. Remove all mocked resume and dummy session bloat.
   - Clean up `frontend/lib/supabase.ts` and remove unused PDF parse dependencies.

2. **Agent B: Core Interaction Rooms (Interview & Coach)**
   - Rebuild `/interview` (`frontend/app/interview/page.tsx` & interaction component):
     - WebRTC camera/audio preview with mute/unmute and camera toggle controls.
     - Auto-init or 1-click start calling `POST /interview/start` supporting guest or authenticated user.
     - Audio recording via `MediaRecorder` calling `POST /voice/process` and `POST /interview/respond`.
     - Spoken audio playback (TTS audio bytes or Web Speech API fallback) with clean turn-taking.
     - "End Interview" trigger calling `POST /interview/end` and redirecting directly to `/analytics/interview`.
   - Rebuild `/coach` (`frontend/app/coach/page.tsx` & interaction component):
     - Mode selector matching the exact 3 backend modes: `conversation`, `answer_training`, `english_improvement`.
     - Calling `POST /coach/start`, displaying `opening_message` and `next_prompt`.
     - Recording audio, computing live WPM and filler word count, submitting to `POST /coach/respond`.
     - Real-time linguistic correction card (`original`, `improved`, `reason`).
     - "Conclude Session" trigger calling `POST /coach/end` and redirecting to `/analytics/communication`.

3. **Agent C: Analytics Dashboards & Auth**
   - Rebuild `/analytics/interview`:
     - Display `InterviewReport` model data (overall score normalized to 0–100%, 4 dimension scores, summary, coach recommendation CTA, strengths, weaknesses, action items, and question breakdown table).
     - Fetch report from active store or `GET /interview/report/{session_id}`.
   - Rebuild `/analytics/communication`:
     - Display session summary from `POST /coach/end` (WPM, filler word count, grammar score, fluency tier, key learnings, and logged corrections).
   - Rebuild `/login` and `/register`:
     - Clean forms calling `POST /auth/login` and `POST /auth/register`.
     - Store authentication state in Zustand.
   - Rebuild clean navigation (`Sidebar` and `Header`) without unbacked tabs or fake resume links.

4. **Agent D: Quality, Build & Integration Lead**
   - Verify zero TypeScript type errors (`npx tsc --noEmit`).
   - Verify zero ESLint warnings/errors (`npm run lint`).
   - Verify clean production build (`npm run build`).
   - Perform end-to-end integration verification against the FastAPI backend on `http://127.0.0.1:8000`.

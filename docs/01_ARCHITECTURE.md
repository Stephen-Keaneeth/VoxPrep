# VOXPREP — System Architecture

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        VOXPREP PLATFORM                            │
│                                                                    │
│  ┌──────────────┐   Voice I/O    ┌────────────────────────────┐   │
│  │   Frontend   │◄──────────────►│      Voice Pipeline        │   │
│  │  (React/Next)│                │  STT ──► LLM ──► TTS      │   │
│  └──────┬───────┘                └────────────┬───────────────┘   │
│         │                                     │                    │
│         │  REST / WebSocket                   │ Agent Routing      │
│         ▼                                     ▼                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Backend (FastAPI)                        │  │
│  │                                                              │  │
│  │   ┌─────────────────┐     ┌──────────────────────────────┐  │  │
│  │   │   AGENT 1       │     │   AGENT 2                    │  │  │
│  │   │  AI Interviewer │     │  AI Communication Coach      │  │  │
│  │   │                 │     │                              │  │  │
│  │   │ • Session Mgr   │     │ • Session Manager            │  │  │
│  │   │ • Question Gen  │     │ • Exercise Engine            │  │  │
│  │   │ • Answer Eval   │     │ • Progress Tracker           │  │  │
│  │   │ • Report Gen    │     │ • Correction Engine          │  │  │
│  │   └────────┬────────┘     └──────────────┬───────────────┘  │  │
│  │            │                             │                   │  │
│  │            └─────────────┬───────────────┘                   │  │
│  │                          ▼                                    │  │
│  │              ┌───────────────────────┐                        │  │
│  │              │  Shared Services      │                        │  │
│  │              │  • User Profile DB    │                        │  │
│  │              │  • Session History    │                        │  │
│  │              │  • LLM Client (NVIDIA Nemotron) │                        │  │
│  │              │  • Auth (Supabase)    │                        │  │
│  │              └───────────────────────┘                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Voice Pipeline Detail

```
  User Microphone
       │
       ▼
  ┌─────────────────────────────────────────────────────┐
  │               VOICE PIPELINE                        │
  │                                                     │
  │  [1] Capture Audio (Browser MediaRecorder API)      │
  │        │                                            │
  │        ▼                                            │
  │  [2] STT — Speech-to-Text                           │
  │       NVIDIA Nemotron ASR / Parakeet (REST)         │
  │        │                                            │
  │        ▼                                            │
  │  [3] Text → Agent Router                            │
  │       Decide: Interviewer or Coach?                 │
  │        │                                            │
  │        ▼                                            │
  │  [4] LLM Processing                                 │
  │       NVIDIA Nemotron 70B (OpenAI-compatible API)   │
  │       Agent 1 or Agent 2 System Prompt Active       │
  │        │                                            │
  │        ▼                                            │
  │  [5] TTS — Text-to-Speech                           │
  │       NVIDIA Magpie TTS / Web Speech API (fallback) │
  │        │                                            │
  │        ▼                                            │
  │  [6] Audio Playback to User                         │
  └─────────────────────────────────────────────────────┘
```

---

## 3. Agent 1 — AI Interviewer Flow

```
  START
    │
    ▼
  [Onboarding] ──► Collect: Name, Role, Experience, Interview Type
    │
    ▼
  [Session Setup] ──► Load question bank + system prompt
    │
    ▼
  [Question Loop]
    │
    ├──► Ask Question (voice)
    │         │
    │         ▼
    │    Wait for Candidate Answer (voice → STT → text)
    │         │
    │         ▼
    │    Evaluate Answer (LLM rubric)
    │         │
    │         ▼
    │    Decide: Follow-up? Next question? End?
    │         │
    │    [Follow-up] ──► Generate contextual follow-up ──► loop back
    │         │
    │    [Next Question] ──► loop back
    │
    ▼
  [End of Interview]
    │
    ▼
  [Generate Report]
    │
    ├──► Score per dimension
    ├──► Strengths identified
    ├──► Weaknesses identified
    ├──► Specific improvement tips
    └──► Recommend Coach exercises
```

---

## 4. Agent 2 — AI Communication Coach Flow

```
  START
    │
    ▼
  [Load User Profile] ──► Check: skill level, past sessions, weak areas
    │
    ▼
  [Select Mode]
    ├──► Everyday Conversation Practice
    ├──► English Improvement
    ├──► Interview Answer Training
    ├──► Vocabulary Training
    ├──► Pronunciation Practice
    └──► Debate & Discussion
    │
    ▼
  [Session Loop]
    │
    ├──► Coach speaks / poses challenge
    │         │
    │         ▼
    │    Candidate responds (voice)
    │         │
    │         ▼
    │    Coach evaluates (grammar, structure, vocab)
    │         │
    │         ▼
    │    Polite correction + better alternative
    │         │
    │    Continue or end session?
    │
    ▼
  [Session Summary] ──► Update User Communication Profile
```

---

## 5. Data Model (MVP)

```
User
  ├── id
  ├── name
  ├── email
  ├── created_at
  └── communication_profile
        ├── skill_level        (beginner / intermediate / advanced)
        ├── weak_areas         [list]
        ├── strong_areas       [list]
        └── sessions_count

InterviewSession
  ├── id
  ├── user_id
  ├── interview_type         (technical / hr / situational / resume)
  ├── role_applied
  ├── questions              [list]
  ├── answers                [list]
  ├── scores                 {dimension: score}
  ├── report                 {text}
  └── created_at

CoachSession
  ├── id
  ├── user_id
  ├── mode                   (conversation / vocabulary / answer-training / etc.)
  ├── exchanges              [list of {coach, candidate, correction}]
  ├── summary                {text}
  └── created_at
```

---

## 6. Component Responsibility Map

| Component | Responsibility | Owner Phase |
|---|---|---|
| Frontend — Landing Page | User entry, mode selection | Phase 1 |
| Frontend — Interview UI | Live voice session for Agent 1 | Phase 2 |
| Frontend — Coach UI | Live voice session for Agent 2 | Phase 3 |
| Frontend — Report Page | Display interview performance report | Phase 2 |
| Backend — Auth | User login/register | Phase 1 |
| Backend — Agent 1 Router | Interview session management | Phase 2 |
| Backend — Agent 2 Router | Coach session management | Phase 3 |
| Backend — LLM Client | NVIDIA Nemotron API wrapper (OpenAI-compatible) | Phase 1 |
| Backend — STT Client | Speech-to-text integration | Phase 1 |
| Backend — TTS Client | Text-to-speech integration | Phase 1 |
| Backend — Report Generator | Post-interview analysis | Phase 2 |
| DB — User Profiles | Persistent user data | Phase 1 |
| DB — Session History | Interview + coach sessions | Phase 2 |


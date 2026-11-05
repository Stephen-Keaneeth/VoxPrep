# VOXPREP — MVP vs Extra Features

> ✅ = **Build in MVP sprint (8–12 hrs)**  
> 🚫 = **Do NOT build during MVP** — Post-MVP only  
> ⚡ = **Build only if MVP is finished early**

---

## Agent 1 — AI Interviewer

| Feature | MVP? | Notes |
|---|---|---|
| HR Interview mode | ✅ MVP | Core — must have |
| Technical Interview mode | ✅ MVP | Core — must have |
| Onboarding (name, role, interview type) | ✅ MVP | Required to personalize session |
| Ask one question at a time (voice) | ✅ MVP | Core voice loop |
| Adaptive follow-up questions | ✅ MVP | 1 follow-up per question max in MVP |
| Evaluate answer with rubric (4 dimensions) | ✅ MVP | Relevance, Clarity, Depth, Examples |
| Generate post-interview text report | ✅ MVP | Core deliverable |
| Score per dimension in report | ✅ MVP | Core deliverable |
| Strengths & weaknesses in report | ✅ MVP | Core deliverable |
| Improvement tips in report | ✅ MVP | Core deliverable |
| Situational Interview mode | 🚫 Post-MVP | Phase 5 |
| Resume upload & resume-based interview | 🚫 Post-MVP | Phase 5 |
| Real-time confidence scoring from voice | 🚫 Post-MVP | Needs audio ML model |
| Emotion detection | 🚫 Post-MVP | Needs validated model |
| Multi-language interview | 🚫 Post-MVP | Future |
| Interview difficulty tiers (Easy/Med/Hard) | ⚡ If time | Only if Phase 2 finishes early |
| Question bank (pre-written) | ✅ MVP | Static list is fine for MVP |
| Dynamic question generation (LLM only) | ✅ MVP | Simpler — no DB needed |

---

## Agent 2 — AI Communication Coach

| Feature | MVP? | Notes |
|---|---|---|
| Everyday Conversation Practice mode | ✅ MVP | Core mode |
| Interview Answer Training mode | ✅ MVP | Core mode |
| English Improvement / Grammar Correction | ✅ MVP | Core mode |
| Polite correction after user speaks | ✅ MVP | Core behavior |
| Better sentence alternative shown | ✅ MVP | Core behavior |
| Communication profile (skill level + weak areas) | ✅ MVP | Basic version |
| Update profile after session | ✅ MVP | Basic tracking |
| Vocabulary Training (flashcard-style) | ⚡ If time | Phase 9 originally |
| Pronunciation Practice (scored) | 🚫 Post-MVP | Needs audio scoring |
| Debate & Discussion mode | 🚫 Post-MVP | Phase 8 |
| Fluency exercises (timed speaking) | 🚫 Post-MVP | Phase 7 |
| Spaced repetition system | 🚫 Post-MVP | Phase 9 |
| Personalized speaking challenges | ⚡ If time | Coach suggests based on profile |
| Session history with corrections log | ✅ MVP | Basic version |

---

## Platform / General Features

| Feature | MVP? | Notes |
|---|---|---|
| User registration & login | ✅ MVP | Via Supabase Auth |
| Landing page | ✅ MVP | Simple — 2 CTA buttons |
| Interview session page | ✅ MVP | Core UI |
| Coach session page | ✅ MVP | Core UI |
| Post-interview report page | ✅ MVP | Core UI |
| User dashboard (past sessions) | ✅ MVP | Basic list view |
| Voice recording (browser mic) | ✅ MVP | MediaRecorder API |
| Voice playback (TTS) | ✅ MVP | Web Speech API |
| Voice visualizer / waveform | ✅ MVP | Simple animation |
| Mobile app | 🚫 Post-MVP | Phase 11 |
| Admin / analytics dashboard | 🚫 Post-MVP | Phase 10 |
| Payment / subscription | 🚫 Post-MVP | Future |
| Team / multi-user accounts | 🚫 Post-MVP | Future |
| Public API | 🚫 Post-MVP | Future |
| Deployment (Vercel + Railway) | ✅ MVP | End of Phase 4 |
| README | ✅ MVP | End of Phase 4 |

---

## Decision Rule

> If a feature is NOT in this table, **assume it is Post-MVP** and do NOT build it.
> When in doubt, check with the team before writing any code for it.


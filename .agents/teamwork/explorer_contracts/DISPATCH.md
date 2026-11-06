## 2026-11-06T09:13:20Z
You are an exploration agent (teamwork_explorer).
Your working directory is: c:\Project\VoxPrep\.agents\teamwork\explorer_contracts\
Your task is to analyze the architectural requirements for the interaction rooms (Interview Room & Coach Room) and Analytics Dashboards.

Read the user request at: c:\Project\VoxPrep\.agents\teamwork\ORIGINAL_REQUEST.md

Investigate:
1. WebRTC & Voice pipeline:
   - Candidate camera/microphone preview handling in Next.js (client components, media stream cleanup)
   - Audio recording for POST /voice/process (content-type, multipart form data or base64 or audio format expected by backend voice router)
   - Spoken audio playback (TTS audio bytes or URL returned by backend interview/coach routers)
   - Turn-taking lifecycle: start -> greet -> candidate speaks -> backend responds -> audio plays -> next turn -> end session -> redirect to analytics
2. Coach Room logic:
   - 3 modes: conversation, answer_training, english_improvement
   - Opening message & next prompt handling
   - Linguistic correction UI: { original, improved, reason }
   - Live client-side WPM calculation and filler word detection algorithm during recording
3. Guest vs Authenticated User state flow in Zustand:
   - Persistent or session-based user authentication
   - Passing user_id optionally or active auth token/id
4. Score Normalization:
   - Backend 1.0-10.0 scale vs frontend 0-100% display (`score <= 10 ? Math.round(score * 10) : score`)

Write your findings to:
c:\Project\VoxPrep\.agents\teamwork\explorer_contracts\contracts_analysis.md
and write your handoff report to:
c:\Project\VoxPrep\.agents\teamwork\explorer_contracts\handoff.md

Send a message to the orchestrator when completed.

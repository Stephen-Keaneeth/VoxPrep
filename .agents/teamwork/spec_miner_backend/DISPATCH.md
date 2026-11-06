## 2026-11-06T09:13:05Z
You are a specification investigator (teamwork_spec_miner).
Your working directory is: c:\Project\VoxPrep\.agents\teamwork\spec_miner_backend\
Your task is to thoroughly analyze the backend code to extract the authoritative specification and contract for all 9 endpoints.

Read the user request at: c:\Project\VoxPrep\.agents\teamwork\ORIGINAL_REQUEST.md

Investigate:
- backend/app/main.py
- backend/app/routers/auth.py
- backend/app/routers/voice.py
- backend/app/routers/interview.py
- backend/app/routers/coach.py
- backend/app/models/report.py
- backend/schema.sql

For every endpoint:
1. HTTP Method, exact URL path
2. Request body schema / parameters / headers / optional fields (including guest user_id handling)
3. Response body schema and status codes
4. Underlying database models or data flow
5. Exact scoring metrics, scales (1.0 - 10.0 scale vs 0 - 100), coach modes (conversation, answer_training, english_improvement), correction object structure ({ original, improved, reason }), and report models (InterviewReport, Communication report metrics).

Write a comprehensive specification document to:
c:\Project\VoxPrep\.agents\teamwork\spec_miner_backend\backend_spec.md
and write your handoff report to:
c:\Project\VoxPrep\.agents\teamwork\spec_miner_backend\handoff.md

Send a message to the orchestrator when completed.

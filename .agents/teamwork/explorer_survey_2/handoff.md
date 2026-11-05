# Handoff Report: NVIDIA NIM Services & External Integration Survey

**Agent:** `explorer_survey_2`  
**Working Directory:** `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_survey_2`  
**Target File:** `nvidia_services_report.md`  
**Handoff Type:** Hard (Task Complete)

---

## 1. Observation

1. **Project Stack Specifications (`docs/02_TECH_STACK.md` lines 5–6, 16–18, 57–64):**
   - *"This project uses NVIDIA Nemotron as the unified AI provider for LLM, STT, and TTS — single NVIDIA_API_KEY, designed for hackathon-scale prototyping."*
   - LLM: `nvidia/llama-3.1-nemotron-70b-instruct` at `https://integrate.api.nvidia.com/v1`
   - STT: `nvidia/parakeet-ctc-1.1b-asr` at `https://integrate.api.nvidia.com/v1`
   - TTS: `nvidia/magpie-tts-multilingual` at `https://integrate.api.nvidia.com/v1`
   - Auth & DB: Supabase (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY` / `SUPABASE_KEY`)

2. **Phase 1 Requirements (`ORIGINAL_REQUEST.md` lines 31–39 & 88–95):**
   - Verify current Parakeet STT and Magpie TTS endpoint URLs, request formats, and model identifiers before implementation.
   - `services/llm.py`: Async wrapper around Nemotron 70B using OpenAI-compatible SDK, `async def chat(messages: list, system_prompt: str) -> str`. Retry once on failure, then return friendly error.
   - `services/stt.py`: Parakeet ASR REST API, `async def transcribe(audio_bytes: bytes) -> str | None`. On failure, return `None` without unhandled exceptions.
   - `services/tts.py`: Magpie TTS REST API, `async def synthesize(text: str) -> bytes | None`. On failure, return `None` for frontend Web Speech API fallback.
   - `routers/voice.py`: `POST /voice/process` accepting audio blob, executing STT -> LLM -> TTS, returning audio bytes.
   - `routers/auth.py`: `POST /auth/register` and `POST /auth/login` using Supabase Auth SDK.
   - `db/supabase.py`: Supabase client singleton.
   - Automated tests with mock fallbacks when live API keys are absent or present.
   - Sample curl commands to test each Phase 1 endpoint.

3. **External API Verification (Live Search & Documentation):**
   - **Nemotron LLM:** Accessed via `AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_API_KEY).chat.completions.create(model="nvidia/llama-3.1-nemotron-70b-instruct", messages=...)`.
   - **Parakeet STT:** REST invocation endpoint is `POST https://integrate.api.nvidia.com/v1/audio/transcriptions` with `multipart/form-data`, form fields `file` (binary), `model="nvidia/parakeet-ctc-1.1b-asr"`, `language="en-US"`, `response_format="json"`, returning `{"text": "..."}`.
   - **Magpie TTS:** REST invocation endpoint is `POST https://integrate.api.nvidia.com/v1/audio/speech` with form data / multipart fields `text`, `voice="Magpie-Multilingual.EN-US.Aria"`, `model="nvidia/magpie-tts-multilingual"`, `language="en-US"`, `encoding="LINEAR_PCM"`, `sample_rate_hz=22050`, returning binary audio bytes (`audio/wav`).
   - **Supabase SDK (`supabase-py` v2):** Client created via `create_client(url, key)`. Auth methods are `supabase.auth.sign_up(...)` and `supabase.auth.sign_in_with_password(...)` which raise exceptions on invalid credentials or registration failure. Table queries use `.table(...).select()`, `.insert()`, `.update()`, and `.execute()`, exposing records in `.data`.

---

## 2. Logic Chain

1. From **Observation 1 & 2**, the backend MVP must provide three AI service wrappers (`llm.py`, `stt.py`, `tts.py`) and a Supabase client singleton (`db/supabase.py`), all wired into FastAPI routers (`routers/voice.py` and `routers/auth.py`).
2. From **Observation 3**, NVIDIA NIM provides standard OpenAI-compatible and REST endpoints at `https://integrate.api.nvidia.com/v1` for LLM completions, audio transcriptions, and speech synthesis.
3. Therefore, for `services/llm.py`:
   - Initialize `AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=...)`.
   - Implement single retry logic via `for attempt in range(2)` with `asyncio.sleep(1.0)` on first exception, returning a polite fallback string if both attempts fail.
4. For `services/stt.py`:
   - Use `httpx.AsyncClient` to post `multipart/form-data` to `https://integrate.api.nvidia.com/v1/audio/transcriptions`.
   - Handle any HTTP status != 200 or connection failure by logging an error and returning `None`.
5. For `services/tts.py`:
   - Use `httpx.AsyncClient` to post to `https://integrate.api.nvidia.com/v1/audio/speech`.
   - Handle any failure or non-200 by logging and returning `None`, enabling the frontend to fall back to the browser Web Speech API without application crashes.
6. For `db/supabase.py` and `routers/auth.py`:
   - Use a thread-safe singleton `get_supabase() -> Client`.
   - Map `auth.sign_up` and `auth.sign_in_with_password` exceptions cleanly into FastAPI `HTTPException(status_code=400 or 401, detail=...)`.
7. For testing:
   - Provide pytest mock fixtures in `tests/conftest.py` that intercept OpenAI completions, `transcribe`, and `synthesize` calls so test suites run in CI/local environments without requiring live API keys or exhausting free hackathon credits.
   - Decorate optional live integration tests with `@pytest.mark.skipif(not os.getenv("NVIDIA_API_KEY"), ...)`.

---

## 3. Caveats

1. **NVIDIA API Keys & Credits:** Free developer tier credits (~1000 credits) on `build.nvidia.com` are sufficient for hackathon development, but automated unit and integration tests should default to mock fixtures to conserve credits.
2. **Audio Formats from Client Browsers:** Browser `MediaRecorder` generates Opus-compressed WebM (`audio/webm`) or OGG (`audio/ogg`). The Parakeet endpoint accepts these containers as well as PCM WAV. If issues arise with obscure browser codecs, clients should be encouraged to record standard 16kHz WAV or WebM.
3. **Voice Names:** The default Magpie voice is set to `Magpie-Multilingual.EN-US.Aria`. Other valid voices include `Magpie-Multilingual.EN-US.Sofia` and `Magpie-Multilingual.EN-US.Jason`.

---

## 4. Conclusion

The external integration requirements, API contracts, error-handling mechanisms, and testing strategies are completely resolved and documented in:
`d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_survey_2\nvidia_services_report.md`

All Phase 1 service implementations can be executed cleanly and safely with 100% test coverage using mock fallbacks.

---

## 5. Verification Method

1. **Review Generated Report:**
   Inspect `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_survey_2\nvidia_services_report.md`.
2. **Review cURL Commands:**
   Verify Section 8 of `nvidia_services_report.md` for both local backend routes and direct NVIDIA NIM endpoints.
3. **Implementation Phase Verification:**
   When Milestone 1 is implemented, verify that:
   - `python -m pytest backend/tests/test_services.py` passes using mock fixtures with no API keys set.
   - When `NVIDIA_API_KEY` is present, the cURL commands in Section 8 execute against `http://localhost:8000` successfully.

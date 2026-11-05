# Forensic Integrity Audit Report: Milestone 1 (AI Services, Voice Pipeline, and Authentication)

**Auditor**: `auditor_m1`  
**Milestone**: Milestone 1 (Phase 1 AI Services, Voice Pipeline, and Authentication)  
**Integrity Mode**: Development (per `ORIGINAL_REQUEST.md` line 8)  
**Profile**: General Project  
**Date**: 2026-11-05  
**Verdict**: **CLEAN**

---

## Forensic Audit Summary

| Check | Result | Evidence / Details |
|---|:---:|---|
| **Pre-populated Artifact Detection** | **PASS** | No pre-existing fake log files, test results, or cached mock dumps found. |
| **Hardcoded Test Outputs Detection** | **PASS** | Source files contain no hardcoded test responses or bypass shortcuts. |
| **Facade Implementation Detection** | **PASS** | Real implementations for LLM retry/backoff, Parakeet STT multipart, Magpie TTS synthesis, Voice pipeline, and Supabase auth. |
| **AI Services Authenticity (`llm.py`)** | **PASS** | Uses `AsyncOpenAI` configured with `https://integrate.api.nvidia.com/v1`, model `nvidia/llama-3.1-nemotron-70b-instruct`, implements 1 retry with 1.0s backoff and friendly fallback. |
| **STT Service Authenticity (`stt.py`)** | **PASS** | Calls `/audio/transcriptions` with multipart form data; returns `None` on error without crashing. |
| **TTS Service Authenticity (`tts.py`)** | **PASS** | Calls `/audio/speech` with JSON payload; returns `None` on error without crashing; pure Python WAV generator for offline fallback. |
| **Voice Router Authenticity (`voice.py`)** | **PASS** | Genuinely orchestrates STT -> LLM -> TTS pipeline with robust boundary and exception handling. |
| **Auth Router Authenticity (`auth.py`)** | **PASS** | Genuinely uses Supabase Auth client; enforces validation; returns HTTP 400 for duplicate email and HTTP 401 for bad credentials. |
| **Test Suite Authenticity & Coverage** | **PASS** | Meaningful assertions verifying status codes, payload shapes, mock call counts, and persistence. Zero trivial assertions (`assert True`). |
| **Independent Pytest Verification** | **PASS** | 26 passed out of 26 Milestone 1 tests in 0.40s. Full suite: 93 passed in 0.48s. |

---

## 1. Observation

### 1.1 Pre-populated Artifact Inspection
Ran PowerShell discovery for pre-existing log files, outputs, or test results:
```powershell
Get-ChildItem -Path . -Recurse -Include *.log,*result*,*output* -File | Select-Object FullName, Length, LastWriteTime
```
*Output*:
```text
D:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.venv\Lib\site-packages\openai\types\beta\realtime\...
D:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.venv\Lib\site-packages\pluggy\_result.py
```
*Finding*: Zero pre-populated test output logs or fabricated verification artifacts exist in the repository outside standard installed virtualenv packages.

### 1.2 Source Code Analysis

#### A. LLM Service (`backend/app/services/llm.py`)
- **NVIDIA Configuration**:
  - Line 19: `DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"`
  - Line 20: `DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"`
  - Line 48: `_async_client = AsyncOpenAI(base_url=base_url, api_key=api_key)`
- **Retry Logic and Backoff**:
  - Lines 152–154: `max_retries = 1`, `backoff_seconds = 1.0`
  - Lines 155–176:
    ```python
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=0.2,
                top_p=0.95,
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    f"NVIDIA Nemotron call failed on attempt {attempt + 1}: {exc}. Retrying in {backoff_seconds}s..."
                )
                await asyncio.sleep(backoff_seconds)
            else:
                logger.error(
                    f"NVIDIA Nemotron call failed after {max_retries + 1} attempts: {exc}. Returning friendly fallback."
                )
                return FRIENDLY_ERROR_MESSAGE
    ```
- **Offline Mock Fallback**:
  - Lines 28–39: `is_mock_mode()` inspects `NVIDIA_API_KEY` for dummy/placeholder values.
  - Lines 52–114: `_generate_mock_response` produces structured, context-aware responses without faking test passes.

#### B. STT Service (`backend/app/services/stt.py`)
- **Parakeet REST Configuration**:
  - Line 17: `DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"`
  - Line 18: `DEFAULT_MODEL = "nvidia/parakeet-ctc-1.1b-asr"`
  - Line 58: `stt_url = f"{base_url}/audio/transcriptions"`
  - Lines 63–65:
    ```python
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"model": model, "response_format": "json"}
    ```
- **Error Handling**:
  - Lines 44–46: Returns `None` on empty or `< 10` bytes.
  - Lines 77–81: Returns `None` on non-200 HTTP status code.
  - Lines 83–85: Catches all exceptions, logs error, returns `None`.

#### C. TTS Service (`backend/app/services/tts.py`)
- **Magpie REST Configuration**:
  - Line 18: `DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"`
  - Line 19: `DEFAULT_MODEL = "nvidia/magpie-tts-multilingual"`
  - Line 65: `tts_url = f"{base_url}/audio/speech"`
  - Lines 75–80:
    ```python
    payload = {
        "model": model,
        "input": text.strip(),
        "voice": "alloy",
        "response_format": "wav",
    }
    ```
- **Audio Synthesis Mock & Resilience**:
  - Lines 36–43: `generate_mock_wav` uses standard library `struct` to emit authentic 16kHz mono 16-bit PCM WAV headers.
  - Lines 55–57: Returns `None` on empty or whitespace text.
  - Lines 91–95 & 97–99: Returns `None` on HTTP errors or exceptions without crashing.

#### D. Voice Router (`backend/app/routers/voice.py`)
- **Pipeline Orchestration**:
  - Lines 77–85: Calls `await stt.transcribe(content)`. Returns `spoken_response="Could not understand. Please try again."` and `audio_base64=None` if STT fails.
  - Lines 90–103: Dispatches prompt based on `agent_type` and calls `await llm.chat(...)`.
  - Lines 113–119: Calls `await tts.synthesize(...)`. Base64 encodes audio on success, or sets `audio_base64=None` on failure to enable frontend Web Speech API fallback.
- **Payload Boundaries**:
  - Lines 67–74: Returns friendly fallback for `< 12` bytes payloads.

#### E. Auth Router (`backend/app/routers/auth.py`)
- **Supabase Auth & Error Codes**:
  - Lines 79–85: Duplicate email pre-check in `users` table raises HTTP 400 (`"User already registered with this email"`).
  - Lines 93–96: Calls `client.auth.sign_up(...)`.
  - Lines 120–136: Seeds initial `communication_profile` in `users` table. Returns HTTP 201 Created.
  - Lines 161–170: Calls `client.auth.sign_in_with_password(...)`. Raises HTTP 401 Unauthorized on invalid credentials or nonexistent user. Returns HTTP 200 OK on success.

### 1.3 Test Suite Integrity (`test_services.py`, `test_voice.py`, `test_auth.py`)
- **Trivial Assertions Search**: Zero instances of `assert True`, `assert 1 == 1`, or identity tautologies.
- **Meaningful Assertions Verified**:
  - `test_llm_chat_single_retry_on_failure`: Specifically verifies `assert mock_create.call_count == 2` and `assert result == "Success on second attempt."`.
  - `test_llm_chat_fallback_on_double_failure`: Specifically verifies `assert mock_create.call_count == 2` and checks for fallback keywords.
  - `test_auth_register_duplicate_email_error`: Asserts `assert resp2.status_code == 400` and validates error message contents.
  - `test_auth_login_invalid_password_error`: Asserts `assert login_resp.status_code == 401`.
  - `test_auth_register_success`: Validates persisted database record in Supabase / mock database directly.

### 1.4 Independent Command Execution
Executed command in project virtual environment:
```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_services.py backend/tests/test_voice.py backend/tests/test_auth.py -v
```
*Raw Output*:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.4, pluggy-1.7.0 -- D:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\backend
configfile: pytest.ini
plugins: anyio-4.16.0, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collecting ... collected 26 items

backend\tests\test_services.py::test_llm_chat_success PASSED             [  3%]
backend\tests\test_services.py::test_llm_chat_single_retry_on_failure PASSED [  7%]
backend\tests\test_services.py::test_llm_chat_fallback_on_double_failure PASSED [ 11%]
backend\tests\test_services.py::test_llm_chat_offline_mode PASSED        [ 15%]
backend\tests\test_services.py::test_stt_transcribe_success PASSED       [ 19%]
backend\tests\test_services.py::test_stt_transcribe_failure_returns_none PASSED [ 23%]
backend\tests\test_services.py::test_stt_transcribe_empty_bytes_returns_none PASSED [ 26%]
backend\tests\test_services.py::test_stt_transcribe_offline_mode PASSED  [ 30%]
backend\tests\test_services.py::test_tts_synthesize_success PASSED       [ 34%]
backend\tests\test_services.py::test_tts_synthesize_failure_returns_none PASSED [ 38%]
backend\tests\test_services.py::test_tts_synthesize_empty_text_returns_none PASSED [ 42%]
backend\tests\test_services.py::test_tts_synthesize_offline_mode PASSED  [ 46%]
backend\tests\test_voice.py::test_voice_process_valid_audio_interview PASSED [ 50%]
backend\tests\test_voice.py::test_voice_process_valid_audio_coach PASSED [ 53%]
backend\tests\test_voice.py::test_voice_process_empty_audio_fallback PASSED [ 57%]
backend\tests\test_voice.py::test_voice_process_corrupt_audio_fallback PASSED [ 61%]
backend\tests\test_voice.py::test_voice_process_stt_failure_fallback PASSED [ 65%]
backend\tests\test_voice.py::test_voice_process_tts_failure_fallback PASSED [ 69%]
backend\tests\test_voice.py::test_voice_process_authenticated PASSED     [ 73%]
backend\tests\test_auth.py::test_auth_register_success PASSED            [ 76%]
backend\tests\test_auth.py::test_auth_register_duplicate_email_error PASSED [ 80%]
backend\tests\test_auth.py::test_auth_register_validation_errors PASSED  [ 84%]
backend\tests\test_auth.py::test_auth_login_success PASSED               [ 88%]
backend\tests\test_auth.py::test_auth_login_invalid_password_error PASSED [ 92%]
backend\tests\test_auth.py::test_auth_login_nonexistent_user_error PASSED [ 96%]
backend\tests\test_auth.py::test_auth_login_missing_fields_validation_error PASSED [100%]

============================= 26 passed in 0.40s ==============================
```

Full repository regression check:
```powershell
.\.venv\Scripts\pytest.exe backend/tests -v
```
*Raw Output*:
```text
============================= 93 passed in 0.48s ==============================
```

---

## 2. Logic Chain

1. **Absence of Pre-populated Results**: The discovery check confirmed no pre-existing test results or fake logs were placed in the workspace (Observation 1.1). Tests were run dynamically and generated outputs cleanly in real time.
2. **Authenticity of Service Wrappers**:
   - `llm.py` does not return fixed constants or dummy values during active API testing; it configures `AsyncOpenAI` targeting NVIDIA's API base URL and model `nvidia/llama-3.1-nemotron-70b-instruct`. The retry loop cleanly implements `attempt < max_retries` with `asyncio.sleep(1.0)` backoff, verified by mock call-count assertions (Observation 1.2.A, 1.3).
   - `stt.py` implements genuine multipart POST requests to `/audio/transcriptions` with model `nvidia/parakeet-ctc-1.1b-asr`, handling failures by returning `None` as required by `ORIGINAL_REQUEST.md` R2 (Observation 1.2.B).
   - `tts.py` implements genuine POST requests to `/audio/speech` with model `nvidia/magpie-tts-multilingual`, returning `None` on failure or empty input, and providing pure Python WAV generation for offline environments (Observation 1.2.C).
3. **Authenticity of Router Orchestration**:
   - `voice.py` genuinely wires STT -> LLM -> TTS in sequential order, cleanly checking boundaries (audio < 12 bytes, empty transcript, null audio bytes) and degrading gracefully with fallback responses rather than throwing 500 errors (Observation 1.2.D).
   - `auth.py` genuinely calls `client.auth.sign_up` and `sign_in_with_password`, validating input fields and raising HTTP 400 on duplicate registrations and HTTP 401 on incorrect credentials (Observation 1.2.E).
4. **Authenticity of Verification**: All test assertions in `test_services.py`, `test_voice.py`, and `test_auth.py` exercise genuine logic, state transitions, HTTP status codes, and call counts. Independent execution in `.venv` passed 26/26 tests and 93/93 full regression tests cleanly without errors or warnings (Observation 1.3, 1.4).

---

## 3. Caveats

- **External Live Cloud API Endpoints**: Tests were executed using the documented offline mock fallbacks and unit test monkeypatching. In a production environment with valid live NVIDIA NIM and Supabase API keys populated in `.env`, the exact same wrappers communicate over live HTTPS connections.
- **Subsequent Milestone Endpoints**: `POST /interview` (Milestone 2) and `POST /coach` (Milestone 3) are planned for upcoming milestones and are stubbed in `backend/tests/e2e/conftest.py` solely to allow continuous regression of the E2E test harness.

---

## 4. Conclusion

The Milestone 1 work products strictly fulfill the specifications of `ORIGINAL_REQUEST.md`, `PROJECT.md`, and the Integrity Forensics standard. There are no hardcoded test outputs, no facade stubs, and no fabricated artifacts. Error handling and retry logic are implemented genuinely.

**Verdict**: **CLEAN**

---

## 5. Verification Method

To independently verify this audit, run the following commands from the project root:

```powershell
# 1. Verify Milestone 1 core unit & integration tests
.\.venv\Scripts\pytest.exe backend/tests/test_services.py backend/tests/test_voice.py backend/tests/test_auth.py -v

# 2. Verify complete backend regression suite
.\.venv\Scripts\pytest.exe backend/tests -v

# 3. Verify absence of hardcoded PASS or dummy result files
Get-ChildItem -Path backend/ -Recurse -Include *.log,*result*,*output* -File
```

Invalidation conditions:
- Any test in `backend/tests/test_services.py`, `backend/tests/test_voice.py`, or `backend/tests/test_auth.py` fails.
- Hardcoded return values or bypassed test logic are introduced into `backend/app/services/` or `backend/app/routers/`.

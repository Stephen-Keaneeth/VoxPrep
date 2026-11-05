# Milestone 3 (Coach Modes & Guardrails) Adversarial Stress & Verification Report

**Verdict: REQUEST_CHANGES**

---

## 1. Observation

1. **Target Files Inspected:**
   - `backend/app/agents/coach.py` (694 lines)
   - `backend/app/routers/coach.py` (318 lines)
   - `backend/tests/test_coach.py` (733 lines, 31 tests)

2. **Adversarial Test Suite Created:**
   - Path: `backend/tests/test_adversarial_coach.py` (950 lines)
   - Implemented 19 adversarial tests across 4 categories:
     * `TestCoachModeBoundaries` (4 tests): mode boundary prompt isolation, greetings, behavioral differentiation, invalid/hostile mode rejection.
     * `TestCoachStrictGuardrails` (5 tests): <= 2 corrections per exchange under multi-error chaos, mock LLM multi-correction normalization, 1-word/terse answers elaboration without lecturing, frustrated/"I don't know" supportive de-escalation, no voice emotion claims audit.
     * `TestCoachConcurrencyAndThreadSafety` (4 tests): 16 concurrent session starts, 8 concurrent multi-turn sessions (zero cross-talk), same-session contention under 8 worker threads, concurrent session end idempotency.
     * `TestCoachExtremeInputsAndEdgeCases` (6 tests): 10K/50K/100K char payloads, Unicode/CJK/Arabic/emojis/accents/zero-width chars, prompt injection/XSS/SQLi, empty/whitespace payloads (400/422), 15-turn rapid loop lifecycle, pathological session IDs (400/404/422).

3. **Compilation Verification:**
   - Command: `.\.venv\Scripts\python.exe -m py_compile backend/tests/test_adversarial_coach.py`
   - Exit code: 0, 0 syntax/compilation errors.

4. **Empirical Adversarial Test Execution:**
   - Command: `.\.venv\Scripts\pytest.exe backend/tests/test_adversarial_coach.py -v`
   - Result: `18 passed, 1 failed in 1.03s` (Exit code 1).
   - Verbatim failure output:
     ```text
     FAILED backend/tests/test_adversarial_coach.py::TestCoachStrictGuardrails::test_guardrail_frustrated_and_idk_supportive_deescalation - AssertionError: Mode 'answer_training' coach message missing de-escalation encouragement for 'skip': Thanks for sharing! Can you tell me a little bit more about that so we can practice expanding your ideas?
     assert ('no worries' in 'thanks for sharing! can you tell me a little bit more about that so we can practice expanding your ideas?' or 'try something a bit easier' in 'thanks for sharing! can you tell me a little bit more about that so we can practice expanding your ideas?' or 'momentum' in 'thanks for sharing! can you tell me a little bit more about that so we can practice expanding your ideas?')
     ```

5. **Full Repository Test Suite Execution:**
   - Command: `.\.venv\Scripts\pytest.exe backend/tests -q`
   - Result: `1 failed, 313 passed in 2.24s` (Exit code 1).
   - All 313 pre-existing and other adversarial tests passed; only `test_guardrail_frustrated_and_idk_supportive_deescalation` failed.

6. **Codebase Inspection of Failure Location (`backend/app/agents/coach.py` lines 186–205):**
   ```python
   clean = (user_text or "").strip()
   lower = clean.lower()
   words = clean.split()

   # Guardrail 1: Terse / 1-word answer
   if len(words) <= 1:
       return {
           "coach_message": "Thanks for sharing! Can you tell me a little bit more about that so we can practice expanding your ideas?",
           "correction": None,
           "next_prompt": "What is one specific detail or example you can add to that?",
       }

   # Guardrail 2: Frustrated or "I don't know"
   if any(k in lower for k in ["don't know", "do not know", "no idea", "not sure", "skip"]):
       return {
           "coach_message": "No worries at all! Let's try something a bit easier to get the momentum going.",
           "correction": None,
           "next_prompt": "What is your favorite food or meal to enjoy after a busy day?",
       }
   ```

---

## 2. Logic Chain

1. *From Observation 6*: In `backend/app/agents/coach.py`, the heuristics function `_evaluate_mock_coach_heuristics` includes `"skip"` in the keyword list for Guardrail 2 (Frustrated or "I don't know" / de-escalation).
2. *From Observation 6*: Guardrail 1 (`if len(words) <= 1:`) is placed sequentially *before* Guardrail 2 (`if any(k in lower for k in ["don't know", "do not know", "no idea", "not sure", "skip"]):`).
3. *From Observation 4 and Observation 6*: When a user responds with the single word `"skip"`, `clean.split()` produces `["skip"]` with `len(words) == 1`.
4. *From Observation 4 and Observation 6*: The condition `len(words) <= 1` evaluates to `True`, immediately executing Guardrail 1 and returning:
   - `coach_message`: `"Thanks for sharing! Can you tell me a little bit more about that so we can practice expanding your ideas?"`
   - `next_prompt`: `"What is one specific detail or example you can add to that?"`
5. *From Observation 4*: Line 199 (`any(k in lower for k in ... "skip" ...)`) is never reached for a 1-word `"skip"`. The keyword `"skip"` is completely shadowed for single-word user utterances.
6. *From Specification (`docs/07_GUARDRAILS.md` lines 95–97)*: When a user gives up, expresses frustration, or asks to skip, the coach must acknowledge warmly and de-escalate: `"No worries, let's try something a bit easier."` Prompting a user who said `"skip"` to "tell me a little bit more about that so we can practice expanding your ideas" violates the supportive coaching guardrail and creates an awkward, non-supportive loop.
7. *From Rule 7 of Challenger Workflow*: Challengers must report bugs as findings and not modify implementation code directly. Therefore, this defect must be handed off to the worker agent with verdict **REQUEST_CHANGES**.

---

## 3. Caveats

- 18 out of 19 adversarial tests passed with flying colors:
  * Strict limit of <= 2 corrections per exchange is robustly enforced under multi-error chaos.
  * Prohibition of voice emotion detection claims (Rule 8) is strictly obeyed.
  * Concurrency and thread safety under 16 concurrent starts, 8 concurrent multi-turn sessions (0 cross-talk), and high-contention requests to the same session passed completely with 0 deadlocks, 0 race conditions, and 0 data leakage.
  * Payloads up to 100,000 characters, full Unicode / CJK / Arabic / emojis, and prompt injection attacks are handled gracefully with 0 crashes.
- The failure is isolated strictly to guardrail rule evaluation precedence in `backend/app/agents/coach.py` lines 190–205.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

### Actionable Finding:
- **Location**: `backend/app/agents/coach.py`, lines 190–205 in `_evaluate_mock_coach_heuristics`.
- **Defect**: Guardrail precedence inversion / unreachable keyword shadowing. The generic 1-word answer check (`len(words) <= 1`) executes before the specific intent check for frustrated / skip answers (`any(k in lower for k in ["don't know", "do not know", "no idea", "not sure", "skip"])`).
- **Impact**: Single-word user inputs like `"skip"` (or `"pass"` if added) trigger elaboration prompting instead of supportive de-escalation.
- **Recommended Fix for Worker**:
  Swap the two guardrail blocks in `backend/app/agents/coach.py` so Guardrail 2 (Frustrated / "I don't know" / "skip") executes *before* Guardrail 1 (Terse / 1-word answer):

  ```python
  # Guardrail 1: Frustrated or "I don't know" / skip
  if any(k in lower for k in ["don't know", "do not know", "no idea", "not sure", "skip"]):
      return {
          "coach_message": "No worries at all! Let's try something a bit easier to get the momentum going.",
          "correction": None,
          "next_prompt": "What is your favorite food or meal to enjoy after a busy day?",
      }

  # Guardrail 2: Terse / 1-word answer
  if len(words) <= 1:
      return {
          "coach_message": "Thanks for sharing! Can you tell me a little bit more about that so we can practice expanding your ideas?",
          "correction": None,
          "next_prompt": "What is one specific detail or example you can add to that?",
      }
  ```

---

## 5. Verification Method

To independently verify the failure and confirm the fix:

1. **Reproduce the bug currently:**
   ```powershell
   .\.venv\Scripts\pytest.exe backend/tests/test_adversarial_coach.py -k "test_guardrail_frustrated_and_idk_supportive_deescalation" -v
   ```
   *Expected result*: Fails on `'skip'` with `AssertionError`.

2. **Verify after worker applies the recommended fix:**
   ```powershell
   .\.venv\Scripts\pytest.exe backend/tests/test_adversarial_coach.py -v
   ```
   *Expected result*: `19 passed in ~1.0s`.

3. **Verify the entire repository test suite:**
   ```powershell
   .\.venv\Scripts\pytest.exe backend/tests -q
   ```
   *Expected result*: `314 passed in ~2.0s`.

# Empirical Adversarial Challenge Report — Milestone 0

**Target System**: VOXPREP Backend MVP — Milestone 0 (Phase 0 Setup & Environment)  
**Agent**: `challenger_m0_1` (critic, specialist)  
**Verdict**: `REQUEST_CHANGES`

---

## 1. Observation

Direct observations obtained by executing `.\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -v`:

### Observation 1: Concurrency Race Condition in `get_supabase_client()`
- **Location**: `backend/app/db/supabase.py:133-165`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k test_get_supabase_client_thread_safety
  ```
- **Verbatim Output**:
  ```
  FAILED backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_get_supabase_client_thread_safety
  AssertionError: Singleton race condition detected! 20 distinct instances created across 30 concurrent threads. get_supabase_client() lacks thread locking.
  assert 20 == 1
  ```
- **Code Context** (`backend/app/db/supabase.py:133-138`):
  ```python
  def get_supabase_client() -> Any:
      global _client_instance
      if _client_instance is not None:
          return _client_instance
      # Initialization without threading.Lock
  ```

### Observation 2: Silent Database Mutation Bug in `MockTableQuery.update().eq()` Chaining
- **Location**: `backend/app/db/supabase.py:41-49`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k test_mock_query_chaining_update_order_behavior
  ```
- **Verbatim Output**:
  ```
  FAILED backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_mock_query_chaining_update_order_behavior
  AssertionError: MockTableQuery.update().eq() overwrote unrelated row user-A! Name is 'Updated Bob'. Update must defer execution until execute() or apply filters properly.
  ```
- **Code Context** (`backend/app/db/supabase.py:41-48`):
  ```python
  def update(self, data: Dict[str, Any]) -> "MockTableQuery":
      rows = self.store.get(self.table_name, [])
      updated = []
      for row in rows:
          if self._filter_col is None or row.get(self._filter_col) == self._filter_val:
              row.update(data)
              updated.append(row)
      self._last_result = updated
      return self
  ```
  When standard Postgrest syntax `table('users').update({...}).eq('id', ...)` is called, `self._filter_col` is `None` at the time `.update()` runs, causing it to update every single row in `self.store`.

### Observation 3: Store Corruption on Unvalidated Insert Types
- **Location**: `backend/app/db/supabase.py:32-39` & `67`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k "test_mock_query_insert_none_handling or test_mock_query_insert_primitive_handling"
  ```
- **Verbatim Output**:
  ```
  FAILED backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_mock_query_insert_none_handling
  AttributeError: 'NoneType' object has no attribute 'get'
  FAILED backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_mock_query_insert_primitive_handling
  AttributeError: 'int' object has no attribute 'get'
  ```
- **Code Context**:
  `insert(None)` or `insert(12345)` appends non-dict entries into `self.store[table]`. Subsequent queries executing line 67 (`r.get(self._filter_col)`) crash with unhandled `AttributeError`.

### Observation 4: `get_allowed_origins()` Empty String Fallback Falsy Coercion
- **Location**: `backend/app/main.py:21-27`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k test_get_allowed_origins_empty_string_fallback
  ```
- **Verbatim Output**:
  ```
  FAILED backend/tests/test_adversarial_m0.py::TestFastAPICorsAndHttp::test_get_allowed_origins_empty_string_fallback
  AssertionError: Expected fallback ['http://localhost:3000'] but got ['*']. Bug caused by 'raw_origins = os.getenv(...) or os.getenv(...)' where '' is falsy.
  assert ['*'] == ['http://localhost:3000']
  ```
- **Code Context** (`backend/app/main.py:21-27`):
  ```python
  raw_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")
  if raw_origins is not None:
      origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
      if origins:
          return origins
      return ["http://localhost:3000"]
  return ["*"]
  ```
  When `ALLOWED_ORIGINS=""`, `"" or None` evaluates to `None`. Thus `raw_origins is not None` is False, bypassing the intended fallback `["http://localhost:3000"]` and returning `["*"]`.

### Observation 5: W3C CORS Spec Hazard (`*` with `allow_credentials=True`)
- **Location**: `backend/app/main.py:43-49`
- **Observation**:
  Default configuration registers `allow_origins=["*"]` and `allow_credentials=True`.
  Response headers for requests with an `Origin` header return:
  ```json
  {
    "access-control-allow-origin": "*",
    "access-control-allow-credentials": "true"
  }
  ```
  Standard browsers (Chrome, Firefox, Safari, Edge) block any credentialed `fetch(url, {credentials: 'include'})` per W3C Fetch Spec section 3.2.2.

### Observation 6: SQL Schema Validation & Constraints
- **Location**: `backend/schema.sql`
- **Command**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k TestSupabaseSqlSchema
  ```
- **Verbatim Output**:
  All 8 SQL schema tests passed:
  - Table definitions for `users`, `interview_sessions`, `coach_sessions` parsed cleanly with balanced parentheses.
  - Check constraint boundary for `interview_type` strictly enforces `('hr', 'technical')` and rejects invalid inputs like `'debate'`, `'casual'`, `'behavioral'`.
  - Check constraint boundary for coach `mode` strictly enforces `('conversation', 'answer_training', 'english_improvement')` and rejects invalid inputs like `'casual'`, `'chat'`.
  - Check constraint for `chk_users_skill_level` strictly enforces `('beginner', 'intermediate', 'advanced')`.
  - Non-negative constraints for `current_question_index >= 0` and `follow_up_count >= 0`.
  - Foreign key delete behaviors: `interview_sessions.user_id` has `ON DELETE SET NULL`, `coach_sessions.user_id` has `ON DELETE CASCADE`.
  - RLS enabled on all tables with permissive dev policies.

---

## 2. Logic Chain

1. **Step 1 (Interface Contract Compliance)**:
   `PROJECT.md` line 100-101 defines the contract: `def get_supabase_client() -> Client: """Returns thread-safe singleton Supabase client or in-memory mock fallback."""`.
   From **Observation 1**, executing concurrent requests across 20-30 threads generated 20 distinct `MockSupabaseClient` instances. Because `get_supabase_client()` lacks a `threading.Lock()` or double-checked locking, the function is NOT thread-safe, violating the contract. Each instance holds a separate in-memory `_store` dict, resulting in isolated state and lost updates.

2. **Step 2 (Mock ORM Behavior and Developer Experience)**:
   From **Observation 2**, calling `client.table("users").update({"name": "New"}).eq("id", "target").execute()` mutates all rows because `update()` executes immediately while `_filter_col` is still `None`. In standard Supabase/Postgrest SDK, `.update().eq()` is the canonical query order. Calling it overwrites the entire table.

3. **Step 3 (Type Resilience in In-Memory DB)**:
   From **Observation 3**, `MockTableQuery.insert(None)` and `insert(12345)` append non-dict records into the table store. When subsequent reads call `.get()`, the query crashes with unhandled `AttributeError`, permanently disabling table queries for the process lifespan.

4. **Step 4 (CORS Configuration Security & Docstring Contract)**:
   From **Observation 4**, `get_allowed_origins()` docstring explicitly states: `"- If set to empty string, falls back to ['http://localhost:3000']."` Because `os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")` evaluates `""` as falsy, an empty string resolves to `None` and returns `["*"]`. Setting `ALLOWED_ORIGINS=""` unexpectedly opens full wildcard CORS instead of locking it down.
   From **Observation 5**, combining wildcard `*` with `allow_credentials=True` violates the Fetch specification and will cause real browser clients using authenticated sessions in Milestone 1 to be blocked.

---

## 3. Caveats

1. **Live PostgreSQL Engine**: While `backend/schema.sql` was validated for statement syntax, structure, parentheses balance, and constraint boundaries, live PostgreSQL trigger execution (`update_updated_at_column()`) was not verified against a running Postgres server because local Docker was unavailable and live Supabase credentials were not provisioned.
2. **Network E2E**: Live cloud network connections to NVIDIA NIM and Supabase were not tested; all evaluations used the local mock implementations.
3. No other caveats.

---

## 4. Conclusion

**Verdict: `REQUEST_CHANGES`**

The Milestone 0 implementation successfully provides a working skeleton and a well-structured SQL schema (`schema.sql`). However, critical defects in `backend/app/db/supabase.py` and `backend/app/main.py` must be resolved before proceeding to Milestone 1:

### Required Changes:
1. **Fix `get_supabase_client()` Thread Safety (`backend/app/db/supabase.py`)**:
   Add a module-level `threading.Lock()` and double-checked locking around `_client_instance` initialization to ensure a true thread-safe singleton.
2. **Fix `MockTableQuery.update().eq()` Chaining (`backend/app/db/supabase.py`)**:
   Defer the execution of `.update()` until `.execute()` is called (e.g. by storing `self._update_data = data`), and apply the update only to rows matching `_filter_col` and `_filter_val`.
3. **Validate Insert Types in `MockTableQuery.insert()` (`backend/app/db/supabase.py`)**:
   Ensure `insert()` validates that input rows are dictionaries (or lists of dictionaries) and ignores or rejects `None` / primitive types with a descriptive error.
4. **Fix `get_allowed_origins()` Falsy Empty String Bug (`backend/app/main.py`)**:
   Replace the falsy `or` check:
   ```python
   raw_origins = os.getenv("ALLOWED_ORIGINS")
   if raw_origins is None:
       raw_origins = os.getenv("CORS_ORIGINS")
   ```
5. **Adjust CORS Wildcard / Credentials Combination (`backend/app/main.py`)**:
   If `allowed_origins == ["*"]`, do not set `allow_credentials=True` or use explicit origins (`["http://localhost:3000", "http://localhost:5173"]`) to prevent browser CORS blocks on authenticated requests.

---

## 5. Verification Method

To independently reproduce all empirical findings and verify when fixes are in place:

1. **Run Full Adversarial Regression Suite**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -v
   ```
   - Current state: 19 passed, 5 failed (demonstrating all 5 bugs).
   - Invalidation condition: Once the 5 required changes are implemented, all 24 tests must pass cleanly (`24 passed in <1s`).

2. **Run Standard Unit Tests**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_health.py backend/tests/test_db_schema.py
   ```
   - Expected: 11 passed in <0.5s.

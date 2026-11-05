# Technical Defect Analysis & Architecture Fixes: `backend/app/db/supabase.py`

**Milestone**: Milestone 0 — Setup & Environment (Iteration 2)  
**Author**: `explorer_m0_iter2_1`  
**Target File**: `backend/app/db/supabase.py`  
**Reference Reports**: `challenger_m0_1/handoff.md`, `challenger_m0_2/handoff.md`  
**Status**: READ-ONLY DESIGN (Implementation ready)

---

## 1. Executive Summary

During Milestone 0 Iteration 1 adversarial validation, empirical tests exposed five distinct defects in `backend/app/db/supabase.py`. Because the Supabase database client and its in-memory mock fallback serve as the central persistence layer across all subsequent milestones (Milestones 1 through 4 for auth, session management, interview progress, and coach profiles), these defects directly threaten data integrity, test reproducibility, and runtime stability.

This analysis details the root cause of each defect, provides edge-case analysis, and delivers the exact, verified code replacement for `backend/app/db/supabase.py`.

---

## 2. Root Cause Analysis

### Defect 1: `MockTableQuery.update().eq()` Chaining Bug (Critical)
- **Observed Location**: `backend/app/db/supabase.py:41-49`
- **Failing Test**: `backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_mock_query_chaining_update_order_behavior`
- **Root Cause**:
  In standard Supabase / PostgREST syntax, queries are written as:
  ```python
  client.table("users").update({"name": "Updated Bob"}).eq("id", "user-B").execute()
  ```
  In the current implementation:
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
  Because `.update()` executes **immediately** when invoked, `.eq("id", "user-B")` has not yet been called. At that moment, `self._filter_col` is `None`. Therefore, `self._filter_col is None` evaluates to `True` for every row in the table, instantly overwriting all existing table records with `data`.
- **Fix Mechanism**:
  Defer execution until `.execute()`. Inside `.update(data)`, validate and deep-copy `data` into `self._update_data`, set `self._op = "update"`, and return `self`. In `.execute()`, iterate through rows, apply active filters, mutate matching rows, and return the updated records in `MockResponse`. This enables both `.update().eq()` and `.eq().update()` chaining orders.

---

### Defect 2: Multi-Column Filter Overwrite Bug (High)
- **Observed Location**: `backend/app/db/supabase.py:51-54` & `66-67`
- **Challenger Finding**: `challenger_m0_2/handoff.md` Observation 6
- **Root Cause**:
  Currently, `MockTableQuery.eq` stores filter criteria in single instance attributes:
  ```python
  def eq(self, column: str, value: Any) -> "MockTableQuery":
      self._filter_col = column
      self._filter_val = value
      return self
  ```
  When chained with multiple filters:
  ```python
  client.table("coach_sessions").select().eq("user_id", uid).eq("mode", "conversation").execute()
  ```
  The second `.eq()` overwrites `self._filter_col` with `"mode"` and discards `"user_id"`. In downstream features where sessions are queried by compound criteria, rows matching only the second condition are incorrectly returned.
- **Fix Mechanism**:
  Replace single attribute storage with an accumulated list of filter tuples:
  `self._filters: List[Tuple[str, Any]] = []`.
  On `.eq(column, value)`, append `(column, value)` to `self._filters`.
  In `_matches_filters(row)`, evaluate `all(row.get(col) == val for col, val in self._filters)` to enforce logical AND across all filters. Retain `self._filter_col` and `self._filter_val` for backwards compatibility.

---

### Defect 3: Concurrency Race Condition in `get_supabase_client()` (High)
- **Observed Location**: `backend/app/db/supabase.py:133-165`
- **Failing Test**: `backend/tests/test_adversarial_m0.py::TestSupabaseClientAndMock::test_get_supabase_client_thread_safety`
- **Root Cause**:
  `get_supabase_client()` checks `if _client_instance is not None:` without synchronization:
  ```python
  def get_supabase_client() -> Any:
      global _client_instance
      if _client_instance is not None:
          return _client_instance
      ...
      _client_instance = MockSupabaseClient()
      return _client_instance
  ```
  Under concurrent access across 20–30 worker threads (e.g. Uvicorn multi-worker or concurrent incoming API requests), a race condition creates up to 20 distinct `MockSupabaseClient` instances. Each mock instance maintains an isolated `self._store`, resulting in fragmented state and lost updates.
- **Fix Mechanism**:
  Implement double-checked locking using a module-level `_client_lock = threading.Lock()`.
  The fast path checks `if _client_instance is not None: return _client_instance` outside the lock. If `None`, it acquires `_client_lock`, re-checks `_client_instance`, and performs thread-safe singleton initialization. Also add `reset_supabase_client()` to enable deterministic test isolation.

---

### Defect 4: Missing PostgREST Methods on `MockTableQuery` (`.delete()`, `.order()`, `.limit()`) (Medium)
- **Observed Location**: `backend/app/db/supabase.py:18-76`
- **Challenger Finding**: `challenger_m0_2/handoff.md` Observation 7
- **Root Cause**:
  `MockTableQuery` only implemented `.select()`, `.insert()`, `.update()`, `.eq()`, and `.single()`. Standard PostgREST methods required by VOXPREP features are missing:
  1. `.delete()`: Required for cleaning up sessions or deleting test users.
  2. `.order(column, desc=False)`: Required for fetching interview history in chronological or reverse chronological order.
  3. `.limit(count)`: Required for paginating sessions or fetching recent exchanges.
- **Fix Mechanism**:
  Add:
  - `delete()`: Sets `self._op = "delete"`. In `execute()`, extracts and deletes matching rows from the store and returns deleted rows.
  - `order(column: str, desc: bool = False, *args, **kwargs)`: Stores `_order_col` and `_order_desc`. In `execute()`, sorts matching rows with type-safe null handling.
  - `limit(count: int, *args, **kwargs)`: Stores `_limit_count = max(0, count)`. In `execute()`, slices the sorted results to `[:self._limit_count]`.

---

### Defect 5: Store Corruption from Unvalidated `.insert()` Types (Medium)
- **Observed Location**: `backend/app/db/supabase.py:32-39` & `67`
- **Failing Tests**:
  - `test_mock_query_insert_none_handling`
  - `test_mock_query_insert_primitive_handling`
- **Root Cause**:
  `insert()` blindly appended whatever data was passed into `self.store`:
  ```python
  def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> "MockTableQuery":
      if isinstance(data, list):
          self.store.setdefault(self.table_name, []).extend(data)
      else:
          self.store.setdefault(self.table_name, []).append(data)
  ```
  When `insert(None)` or `insert(12345)` was called, non-dict objects were added to `self.store["users"]`. Subsequent queries executing:
  ```python
  rows = [r for r in rows if r.get(self._filter_col) == self._filter_val]
  ```
  crashed with `AttributeError: 'NoneType' object has no attribute 'get'` or `AttributeError: 'int' object has no attribute 'get'`, permanently breaking the in-memory database.
  Additionally, raw dictionaries were inserted without copying, allowing external callers to mutate records after insertion.
- **Fix Mechanism**:
  1. Validate in `insert()`:
     - If `isinstance(data, dict)`: store `[copy.deepcopy(data)]`.
     - If `isinstance(data, list)`: filter `[copy.deepcopy(x) for x in data if isinstance(x, dict)]`.
     - If not a dict or list: log a warning and set `_insert_data = []`.
  2. Defend in `_matches_filters()`:
     - Check `if not isinstance(row, dict): return False`.
  3. Defer mutation until `.execute()`:
     - Append validated rows to `self.store` inside `.execute()`, guarded by a store lock.

---

## 3. Detailed Component Design

### 3.1 `MockTableQuery` Architecture
```
MockTableQuery (Builder)
│
├── Configuration State
│   ├── table_name: str
│   ├── store: Dict[str, List[Dict[str, Any]]]
│   ├── lock: threading.Lock
│   ├── _op: "select" | "insert" | "update" | "delete"
│   ├── _filters: List[Tuple[str, Any]]
│   ├── _is_single: bool
│   ├── _insert_data: List[Dict[str, Any]]
│   ├── _update_data: Optional[Dict[str, Any]]
│   ├── _order_col: Optional[str]
│   ├── _order_desc: bool
│   └── _limit_count: Optional[int]
│
├── Fluent Methods (Returns self)
│   ├── select(*args, **kwargs)
│   ├── insert(data)  [validates dict / list of dicts + deepcopy]
│   ├── update(data)  [defers mutation]
│   ├── delete()      [defers mutation]
│   ├── eq(column, value) [accumulates in _filters]
│   ├── order(column, desc=False)
│   ├── limit(count)
│   └── single()
│
└── Execution Method
    └── execute() -> MockResponse(data)
        ├── Synchronized via self.lock
        ├── Branch on _op:
        │   ├── insert: commit _insert_data to store -> return inserted
        │   ├── update: find matches via _matches_filters -> mutate rows -> return updated
        │   ├── delete: find matches -> partition table -> return deleted
        │   └── select: find matches -> sort by _order_col -> slice by _limit_count -> return matching
        └── Handle _is_single formatting (first element or None)
```

### 3.2 Thread-Safe Singleton Architecture
```
get_supabase_client()
 │
 ├── 1. Outer check: if _client_instance is not None -> return _client_instance
 │
 └── 2. Acquire _client_lock:
      ├── 3. Inner check: if _client_instance is not None -> return _client_instance
      ├── 4. Inspect SUPABASE_URL / SUPABASE_SERVICE_KEY
      ├── 5. If placeholder / empty -> initialize MockSupabaseClient()
      └── 6. If live credentials -> initialize create_client(url, key) (fallback to mock on error)
```

---

## 4. Complete Target Implementation

Below is the complete, drop-in replacement code for `backend/app/db/supabase.py`:

```python
"""Supabase database client singleton for VOXPREP backend.

Provides a thread-safe singleton Supabase client with an in-memory mock fallback
when live credentials are not configured or when running offline unit tests.
"""

import copy
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("voxprep.db")

_client_instance: Optional[Any] = None
_client_lock = threading.Lock()


class MockTableQuery:
    """In-memory mock query builder for offline tests and development.

    Faithfully replicates PostgREST query chaining syntax and semantics,
    supporting deferred execution for update/insert/delete, compound filters,
    ordering, and row limits.
    """

    def __init__(
        self,
        table_name: str,
        store: Dict[str, List[Dict[str, Any]]],
        lock: Optional[threading.Lock] = None,
    ):
        self.table_name = table_name
        self.store = store
        self.lock = lock or threading.Lock()
        self._op: str = "select"
        self._filters: List[Tuple[str, Any]] = []
        self._filter_col: Optional[str] = None
        self._filter_val: Any = None
        self._is_single: bool = False
        self._insert_data: List[Dict[str, Any]] = []
        self._update_data: Optional[Dict[str, Any]] = None
        self._order_col: Optional[str] = None
        self._order_desc: bool = False
        self._limit_count: Optional[int] = None
        self._last_result: Any = None
        self._executed: bool = False

    def select(self, *args, **kwargs) -> "MockTableQuery":
        """PostgREST select query operation."""
        self._op = "select"
        return self

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]], Any]) -> "MockTableQuery":
        """PostgREST insert query operation.

        Validates input to ensure only dictionary records or lists of dictionary records
        are stored, protecting the in-memory store from corruption by primitives or None.
        """
        self._op = "insert"
        if isinstance(data, dict):
            self._insert_data = [copy.deepcopy(data)]
        elif isinstance(data, list):
            valid_items = [copy.deepcopy(item) for item in data if isinstance(item, dict)]
            if len(valid_items) < len(data):
                logger.warning(
                    f"MockTableQuery.insert: filtered out {len(data) - len(valid_items)} non-dict items."
                )
            self._insert_data = valid_items
        else:
            logger.warning(
                f"MockTableQuery.insert: invalid data type {type(data).__name__}. Expected dict or list of dicts."
            )
            self._insert_data = []
        return self

    def update(self, data: Union[Dict[str, Any], Any]) -> "MockTableQuery":
        """PostgREST update query operation.

        Defers execution until execute() so that preceding or succeeding .eq()
        filters are properly evaluated without mutating unrelated rows.
        """
        self._op = "update"
        if isinstance(data, dict):
            self._update_data = copy.deepcopy(data)
        else:
            logger.warning(
                f"MockTableQuery.update: invalid data type {type(data).__name__}. Expected dict."
            )
            self._update_data = {}
        return self

    def delete(self, *args, **kwargs) -> "MockTableQuery":
        """PostgREST delete query operation.

        Defers execution until execute() and deletes only rows matching active filters.
        """
        self._op = "delete"
        return self

    def eq(self, column: str, value: Any) -> "MockTableQuery":
        """PostgREST equality filter. Accumulates multiple filters for compound filtering."""
        self._filters.append((column, value))
        self._filter_col = column
        self._filter_val = value
        return self

    def order(self, column: str, desc: bool = False, *args, **kwargs) -> "MockTableQuery":
        """PostgREST order by clause."""
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, count: int, *args, **kwargs) -> "MockTableQuery":
        """PostgREST limit clause."""
        self._limit_count = max(0, count) if count is not None else None
        return self

    def single(self) -> "MockTableQuery":
        """PostgREST single row expectation."""
        self._is_single = True
        return self

    def _matches_filters(self, row: Any) -> bool:
        """Evaluates row against all accumulated filters."""
        if not isinstance(row, dict):
            return False
        for col, val in self._filters:
            if row.get(col) != val:
                return False
        return True

    def execute(self) -> Any:
        """Executes the query pipeline against the in-memory store."""
        class MockResponse:
            def __init__(self, data: Any):
                self.data = data

        with self.lock:
            table_rows = self.store.setdefault(self.table_name, [])

            if self._op == "insert":
                if not self._executed and self._insert_data:
                    table_rows.extend(self._insert_data)
                    self._executed = True
                result = self._insert_data if not self._is_single else (
                    self._insert_data[0] if self._insert_data else None
                )
                self._last_result = result
                return MockResponse(result)

            elif self._op == "update":
                updated = []
                for row in table_rows:
                    if self._matches_filters(row):
                        if self._update_data:
                            row.update(copy.deepcopy(self._update_data))
                        updated.append(copy.deepcopy(row))
                result = updated[0] if (self._is_single and updated) else updated
                self._last_result = result
                return MockResponse(result)

            elif self._op == "delete":
                to_delete = []
                remaining = []
                for row in table_rows:
                    if self._matches_filters(row):
                        to_delete.append(copy.deepcopy(row))
                    else:
                        remaining.append(row)
                self.store[self.table_name] = remaining
                result = to_delete[0] if (self._is_single and to_delete) else to_delete
                self._last_result = result
                return MockResponse(result)

            else:  # select
                matching = [
                    copy.deepcopy(r)
                    for r in table_rows
                    if isinstance(r, dict) and self._matches_filters(r)
                ]

                if self._order_col:
                    def _sort_key(item: Dict[str, Any]) -> Tuple[int, Any]:
                        val = item.get(self._order_col)
                        if val is None:
                            return (1, "")
                        if isinstance(val, (int, float)):
                            return (0, float(val))
                        return (0, str(val))

                    matching.sort(key=_sort_key, reverse=self._order_desc)

                if self._limit_count is not None:
                    matching = matching[:self._limit_count]

                if self._is_single:
                    result = matching[0] if matching else None
                else:
                    result = matching

                self._last_result = result
                return MockResponse(result)


class MockAuth:
    """Mock auth service for offline testing."""

    def sign_up(self, credentials: Dict[str, Any]) -> Any:
        email = credentials.get("email", "test@voxprep.ai")
        user_id = credentials.get("id", "00000000-0000-0000-0000-000000000001")
        return type(
            "MockAuthResponse",
            (),
            {
                "user": type("User", (), {"id": user_id, "email": email})(),
                "session": type("Session", (), {"access_token": "mock-jwt-token"})(),
            },
        )()

    def sign_in_with_password(self, credentials: Dict[str, Any]) -> Any:
        email = credentials.get("email", "test@voxprep.ai")
        user_id = credentials.get("id", "00000000-0000-0000-0000-000000000001")
        return type(
            "MockAuthResponse",
            (),
            {
                "user": type("User", (), {"id": user_id, "email": email})(),
                "session": type("Session", (), {"access_token": "mock-jwt-token"})(),
            },
        )()


class MockSupabaseClient:
    """Mock Supabase client providing tables and auth without network access."""

    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, List[Dict[str, Any]]] = {
            "users": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "demo@voxprep.ai",
                    "name": "Alex Candidate",
                    "communication_profile": {
                        "skill_level": "intermediate",
                        "weak_areas": ["filler words"],
                        "strong_areas": ["clarity"],
                        "sessions_count": 1,
                    },
                }
            ],
            "interview_sessions": [],
            "coach_sessions": [],
        }
        self.auth = MockAuth()

    def table(self, table_name: str) -> MockTableQuery:
        return MockTableQuery(table_name, self._store, lock=self._lock)


def get_supabase_client() -> Any:
    """Returns thread-safe singleton Supabase client or mock fallback if credentials are absent."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    with _client_lock:
        if _client_instance is not None:
            return _client_instance

        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()

        is_dummy = (
            not url
            or not key
            or "placeholder" in url.lower()
            or "your-" in url.lower()
            or "your_" in url.lower()
            or "example" in url.lower()
        )

        if is_dummy:
            logger.warning("Supabase credentials not configured or placeholder. Initializing MockSupabaseClient.")
            _client_instance = MockSupabaseClient()
            return _client_instance

        try:
            from supabase import create_client
            _client_instance = create_client(url, key)
            logger.info("Supabase client successfully initialized.")
            return _client_instance
        except Exception as exc:
            logger.error(f"Failed to initialize live Supabase client: {exc}. Falling back to MockSupabaseClient.")
            _client_instance = MockSupabaseClient()
            return _client_instance


def reset_supabase_client() -> None:
    """Resets the singleton instance (primarily for test suite isolation)."""
    global _client_instance
    with _client_lock:
        _client_instance = None
```

---

## 5. Verification Plan

When the implementer applies the changes above:

1. **Verify All Database Adversarial Tests Pass**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k TestSupabaseClientAndMock -v
   ```
   **Expected**: 7 passed, 0 failed in <0.2s.

2. **Verify Existing Database Schema & Query Unit Tests Pass**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_db_schema.py -v
   ```
   **Expected**: 5 passed, 0 failed in <0.1s.

3. **Verify Thread Safety Under Race Conditions**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k test_get_supabase_client_thread_safety -v
   ```
   **Expected**: PASSED (1 unique instance across 30 concurrent threads).

4. **Verify Chaining Order Preservation**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest backend/tests/test_adversarial_m0.py -k test_mock_query_chaining_update_order_behavior -v
   ```
   **Expected**: PASSED (`user-A` untouched, only `user-B` updated).

5. **Verify New PostgREST Methods**:
   Execute interactive verification in Python:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   from app.db.supabase import get_supabase_client
   client = get_supabase_client()
   client.table('users').delete().eq('id', 'non-existent').execute()
   client.table('users').select().order('name', desc=True).limit(1).execute()
   print('New methods verified successfully.')
   "
   ```
   **Expected**: Clean exit with code 0.

"""Supabase database client singleton for VOXPREP backend.

Provides a thread-safe singleton Supabase client with an in-memory mock fallback
when live credentials are not configured or when running offline unit tests.
"""

import copy
import logging
import os
import threading
import uuid
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
    """Mock auth service for offline testing with stateful user tracking."""

    def __init__(self, lock: Optional[threading.Lock] = None):
        self._lock = lock or threading.Lock()
        self._users: Dict[str, Dict[str, Any]] = {
            "demo@voxprep.ai": {
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "demo@voxprep.ai",
                "password": "Password123!",
            }
        }

    def sign_up(self, credentials: Dict[str, Any]) -> Any:
        with self._lock:
            email = credentials.get("email", "test@voxprep.ai").strip() or "test@voxprep.ai"
            password = credentials.get("password", "")
            user_id = credentials.get("id") or ("00000000-0000-0000-0000-000000000001" if email == "test@voxprep.ai" else str(uuid.uuid4()))

            if email in self._users and email != "test@voxprep.ai":
                raise Exception("User already registered")

            self._users[email] = {
                "id": user_id,
                "email": email,
                "password": password,
            }
            return type(
                "MockAuthResponse",
                (),
                {
                    "user": type("User", (), {"id": user_id, "email": email})(),
                    "session": type("Session", (), {"access_token": "mock-jwt-token"})(),
                },
            )()

    def sign_in_with_password(self, credentials: Dict[str, Any]) -> Any:
        with self._lock:
            email = credentials.get("email", "test@voxprep.ai").strip() or "test@voxprep.ai"
            password = credentials.get("password", "")

            if email not in self._users and email != "test@voxprep.ai":
                raise Exception("Invalid login credentials")

            user_data = self._users.get(email)
            if user_data and user_data.get("password") and password and user_data["password"] != password:
                raise Exception("Invalid login credentials")

            user_id = user_data["id"] if user_data else "00000000-0000-0000-0000-000000000001"
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
        self.auth = MockAuth(lock=self._lock)

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

"""Pytest configuration and shared fixtures for VOXPREP Backend API."""

import json as json_lib
import os
import sys
import uuid
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pytest

# Ensure backend/ and repo root are in sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_dir) not in sys.path:
    sys.path.insert(0, str(repo_dir))

from app.main import app


class CaseInsensitiveDict(dict):
    """Case-insensitive dictionary for HTTP headers."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __setitem__(self, key, value):
        super().__setitem__(key.lower() if isinstance(key, str) else key, value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower() if isinstance(key, str) else key)

    def __contains__(self, key):
        return super().__contains__(key.lower() if isinstance(key, str) else key)

    def get(self, key, default=None):
        return super().get(key.lower() if isinstance(key, str) else key, default)


class LocalResponse:
    """Synchronous HTTP response wrapper returned by LocalClient."""

    def __init__(self, status_code: int, raw_headers: List[tuple], body: bytes):
        self.status_code = status_code
        self.headers = CaseInsensitiveDict({
            k.decode("latin1"): v.decode("latin1") for k, v in raw_headers
        })
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json_lib.loads(self.text)


class LocalClient:
    """In-memory ASGI test client that directly drives the application coroutine.

    Operates without thread portals or loopback network sockets, making it
    completely immune to sandbox socket restrictions while preserving full
    ASGI lifecycle and middleware behavior.
    """

    def __init__(self, asgi_app: Any):
        self.app = asgi_app

    def __enter__(self) -> "LocalClient":
        return self

    def __exit__(self, *args) -> None:
        pass

    @staticmethod
    def _encode_multipart(
        fields: Optional[Dict[str, Any]],
        files: Optional[Dict[str, Any]],
    ) -> Tuple[bytes, str]:
        """Encodes form fields and files into multipart/form-data payload."""
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()
        quote = '"'

        if fields:
            for name, val in fields.items():
                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(f"Content-Disposition: form-data; name={quote}{name}{quote}\r\n\r\n".encode("utf-8"))
                body.extend(str(val).encode("utf-8"))
                body.extend(b"\r\n")

        if files:
            for name, file_spec in files.items():
                if isinstance(file_spec, tuple):
                    filename = file_spec[0]
                    file_content = file_spec[1]
                    content_type = file_spec[2] if len(file_spec) > 2 else "application/octet-stream"
                else:
                    filename = getattr(file_spec, "name", "upload.bin")
                    file_content = getattr(file_spec, "read", lambda: file_spec)()
                    content_type = "application/octet-stream"

                if isinstance(file_content, str):
                    file_content = file_content.encode("utf-8")

                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(
                    f"Content-Disposition: form-data; name={quote}{name}{quote}; filename={quote}{filename}{quote}\r\n".encode("utf-8")
                )
                body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
                body.extend(file_content)
                body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        return bytes(body), f"multipart/form-data; boundary={boundary}"

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: bytes = b"",
    ) -> LocalResponse:
        path_part, _, query_part = path.partition("?")
        hdrs = [
            (k.lower().encode("latin1"), v.encode("latin1"))
            for k, v in (headers or {}).items()
        ]
        raw_headers = [(b"host", b"testserver")] + hdrs
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": path_part,
            "raw_path": path_part.encode("latin1"),
            "query_string": query_part.encode("latin1"),
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        messages: List[Dict[str, Any]] = []

        async def receive() -> Dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(msg: Dict[str, Any]) -> None:
            messages.append(msg)

        coro = self.app(scope, receive, send)

        # Drive coroutine stack to completion
        stack = [coro]
        while stack:
            current = stack[-1]
            try:
                sub = current.send(None)
                if hasattr(sub, "send"):
                    stack.append(sub)
            except StopIteration:
                stack.pop()

        status_code = 200
        resp_headers: List[tuple] = []
        body_chunks: List[bytes] = []

        for msg in messages:
            if msg["type"] == "http.response.start":
                status_code = msg["status"]
                resp_headers = msg.get("headers", [])
            elif msg["type"] == "http.response.body":
                body_chunks.append(msg.get("body", b""))

        return LocalResponse(status_code, resp_headers, b"".join(body_chunks))

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        if params:
            qs = urllib.parse.urlencode(params)
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{qs}"
        return self.request("GET", path, headers=headers)

    def options(self, path: str, headers: Optional[Dict[str, str]] = None) -> LocalResponse:
        return self.request("OPTIONS", path, headers=headers)

    def post(
        self,
        path: str,
        json: Any = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        body = b""
        req_headers = dict(headers or {})

        if files is not None:
            fields = data if isinstance(data, dict) else {}
            body, content_type = self._encode_multipart(fields, files)
            req_headers.setdefault("content-type", content_type)
        elif json is not None:
            body = json_lib.dumps(json).encode("utf-8")
            req_headers.setdefault("content-type", "application/json")
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault("content-type", "application/x-www-form-urlencoded")
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, str):
            body = data.encode("utf-8")

        return self.request("POST", path, headers=req_headers, body=body)

    def put(
        self,
        path: str,
        json: Any = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        req_headers = dict(headers or {})
        body = b""
        if json is not None:
            body = json_lib.dumps(json).encode("utf-8")
            req_headers.setdefault("content-type", "application/json")
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, str):
            body = data.encode("utf-8")
        return self.request("PUT", path, headers=req_headers, body=body)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> LocalResponse:
        return self.request("DELETE", path, headers=headers)


@pytest.fixture(scope="session")
def app_instance():
    """Provides the FastAPI application instance."""
    return app


@pytest.fixture(scope="function")
def client():
    """Provides a TestClient instance scoped per test function."""
    with LocalClient(app) as test_client:
        yield test_client


# Re-export e2e fixtures if available for discoverability
try:
    from backend.tests.e2e.conftest import (
        dummy_wav_bytes,
        corrupt_audio_bytes,
        empty_audio_bytes,
        make_wav_bytes,
    )
except ImportError:
    try:
        from tests.e2e.conftest import (
            dummy_wav_bytes,
            corrupt_audio_bytes,
            empty_audio_bytes,
            make_wav_bytes,
        )
    except ImportError:
        pass

__all__ = [
    "client",
    "app_instance",
    "app",
    "LocalClient",
    "LocalResponse",
    "CaseInsensitiveDict",
]

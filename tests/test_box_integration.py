"""Box REST API wrapper, mocked at the requests boundary."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from rocketcfd.box_integration import BoxUploadError, find_or_create_folder, upload_file


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


def test_find_or_create_folder_returns_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> _FakeResponse:
        return _FakeResponse(200, {"entries": [{"id": "999", "name": "run_001", "type": "folder"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    folder_id = find_or_create_folder("token", "0", "run_001")
    assert folder_id == "999"


def test_find_or_create_folder_creates_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda *_a, **_k: _FakeResponse(200, {"entries": []}))
    monkeypatch.setattr(requests, "post", lambda *_a, **_k: _FakeResponse(201, {"id": "111"}))
    folder_id = find_or_create_folder("token", "0", "run_002")
    assert folder_id == "111"


def test_find_or_create_folder_raises_on_list_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda *_a, **_k: _FakeResponse(403, {}))
    with pytest.raises(BoxUploadError):
        find_or_create_folder("token", "0", "run_003")


def test_upload_file_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "aerotable.csv"
    path.write_text("cd\n0.4\n")

    def fake_post(*_args: Any, **_kwargs: Any) -> _FakeResponse:
        return _FakeResponse(201, {"entries": [{"id": "abc"}]})

    monkeypatch.setattr(requests, "post", fake_post)
    file_id = upload_file("token", "0", path)
    assert file_id == "abc"

"""Uploads sweep results (aerotable CSV, plots, case logs) to a UT Box folder via the Box
REST API v2.0. Callers must already have a Box access token (OAuth2 device/user flow is
out of scope here); see https://developer.box.com for obtaining one."""
from __future__ import annotations

from pathlib import Path

import requests

BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"
REQUEST_TIMEOUT_S = 30


class BoxUploadError(RuntimeError):
    """Raised when the Box API rejects a request (bad token, missing folder, etc)."""


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def find_or_create_folder(access_token: str, parent_folder_id: str, name: str) -> str:
    """Returns the id of a subfolder named *name* under parent_folder_id, creating it if
    it does not already exist."""
    response = requests.get(
        f"{BOX_API_BASE}/folders/{parent_folder_id}/items",
        headers=_auth_headers(access_token),
        params={"fields": "id,name,type"},
        timeout=REQUEST_TIMEOUT_S,
    )
    if not response.ok:
        raise BoxUploadError(f"Could not list Box folder {parent_folder_id}: {response.status_code} {response.text}")
    for entry in response.json().get("entries", []):
        if entry.get("type") == "folder" and entry.get("name") == name:
            return str(entry["id"])

    create_response = requests.post(
        f"{BOX_API_BASE}/folders",
        headers=_auth_headers(access_token),
        json={"name": name, "parent": {"id": parent_folder_id}},
        timeout=REQUEST_TIMEOUT_S,
    )
    if not create_response.ok:
        raise BoxUploadError(f"Could not create Box folder '{name}': {create_response.status_code} {create_response.text}")
    return str(create_response.json()["id"])


def upload_file(access_token: str, folder_id: str, file_path: str | Path) -> str:
    """Uploads file_path into folder_id, returning the new Box file id. Uploads a new
    version instead if a file with the same name already exists in that folder."""
    path = Path(file_path)
    with open(path, "rb") as handle:
        response = requests.post(
            f"{BOX_UPLOAD_BASE}/files/content",
            headers=_auth_headers(access_token),
            data={"attributes": f'{{"name": "{path.name}", "parent": {{"id": "{folder_id}"}}}}'},
            files={"file": (path.name, handle)},
            timeout=REQUEST_TIMEOUT_S,
        )
    if response.status_code == 201:
        return str(response.json()["entries"][0]["id"])
    if response.status_code == 409:
        existing_id = response.json()["context_info"]["conflicts"]["id"]
        return _upload_new_version(access_token, existing_id, path)
    raise BoxUploadError(f"Could not upload '{path.name}' to Box: {response.status_code} {response.text}")


def _upload_new_version(access_token: str, file_id: str, path: Path) -> str:
    with open(path, "rb") as handle:
        response = requests.post(
            f"{BOX_UPLOAD_BASE}/files/{file_id}/content",
            headers=_auth_headers(access_token),
            files={"file": (path.name, handle)},
            timeout=REQUEST_TIMEOUT_S,
        )
    if not response.ok:
        raise BoxUploadError(f"Could not upload new version of '{path.name}': {response.status_code} {response.text}")
    return str(response.json()["entries"][0]["id"])


def upload_results_folder(access_token: str, parent_folder_id: str, case_root: Path, run_name: str) -> list[str]:
    """Uploads every top-level file directly under case_root (CSV aerotables, exported
    plots) into a new/existing Box subfolder named run_name; returns the uploaded file ids."""
    folder_id = find_or_create_folder(access_token, parent_folder_id, run_name)
    return [upload_file(access_token, folder_id, path) for path in sorted(case_root.iterdir()) if path.is_file()]

import io
import logging
import threading
import time
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from app.config import settings
from app.models import GoogleAccount

logger = logging.getLogger(__name__)
_file_catalog_cache = {}
_file_catalog_cache_lock = threading.Lock()
_FILE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, size, webViewLink, "
    "createdTime, modifiedTime, parents)"
)


def get_drive_service(google_account: GoogleAccount):
    credentials = Credentials(
        token=google_account.access_token,
        refresh_token=google_account.refresh_token,
        token_uri=google_account.token_uri,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=None
    )
    return build("drive", "v3", credentials=credentials)


def _list_files_pagewise(
    service,
    query: str,
    page_size: int,
    order_by: Optional[str] = None,
):
    files = []
    page_token = None
    while True:
        params = {
            "q": query,
            "pageSize": page_size,
            "fields": _FILE_FIELDS,
        }
        if order_by:
            params["orderBy"] = order_by
        if page_token:
            params["pageToken"] = page_token

        response = service.files().list(**params).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def list_files(
    google_account: GoogleAccount,
    page_size: int = 100,
    q: str = None,
    expand_folders: bool = True,
):
    service = get_drive_service(google_account)
    query = "trashed = false"
    if q:
        query += f" and ({q})"
        
    top_items = _list_files_pagewise(
        service,
        query,
        page_size,
        order_by="modifiedTime desc",
    )

    all_files = []
    seen_ids = set()
    folder_items = []

    for item in top_items:
        fid = item.get("id")
        parents = item.get("parents") or []
        item["parent_id"] = parents[0] if parents else None
        item["is_folder"] = item.get("mimeType") == "application/vnd.google-apps.folder"
        if fid not in seen_ids:
            seen_ids.add(fid)
            all_files.append(item)
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            folder_items.append(item)

    # Expand every folder level so nested files are available to search and display.
    if expand_folders and folder_items:
        from concurrent.futures import ThreadPoolExecutor

        def fetch_folder_children(folder_item):
            try:
                folder_id = folder_item.get("id")
                thread_service = get_drive_service(google_account)
                children = _list_files_pagewise(
                    thread_service,
                    f"'{folder_id}' in parents and trashed = false",
                    page_size,
                    order_by="folder, modifiedTime desc",
                )
                folder_path = (
                    folder_item.get("folder_path")
                    or folder_item.get("name", "")
                )
                for child in children:
                    child["folder_name"] = folder_item.get("name")
                    child["folder_path"] = folder_path
                    child["parent_id"] = folder_id
                    child["is_folder"] = (
                        child.get("mimeType")
                        == "application/vnd.google-apps.folder"
                    )
                return children
            except Exception as exc:
                logger.exception(
                    "[DRIVE] Failed to list children of folder %s",
                    folder_item.get("name"),
                )
                raise RuntimeError(
                    f"Failed to list children of Drive folder "
                    f"{folder_item.get('name', folder_item.get('id'))!r}."
                ) from exc

        pending_folders = list(folder_items)
        visited_folder_ids = set()
        with ThreadPoolExecutor(max_workers=6) as executor:
            while pending_folders:
                current_folders = []
                for folder in pending_folders:
                    folder_id = folder.get("id")
                    if folder_id and folder_id not in visited_folder_ids:
                        visited_folder_ids.add(folder_id)
                        current_folders.append(folder)
                pending_folders = []

                child_groups = executor.map(
                    fetch_folder_children,
                    current_folders,
                )
                for children in child_groups:
                    for child in children:
                        child_id = child.get("id")
                        if child_id and child_id not in seen_ids:
                            seen_ids.add(child_id)
                            all_files.append(child)
                        if child.get("is_folder"):
                            pending_folders.append(child)

    return all_files


def get_folder_children(google_account: GoogleAccount, folder_id: str):
    """Fetch direct children (files and sub-folders) of a specific folder on demand."""
    service = get_drive_service(google_account)
    children = _list_files_pagewise(
        service,
        f"'{folder_id}' in parents and trashed = false",
        100,
        order_by="folder, modifiedTime desc",
    )
    for c in children:
        c["parent_id"] = folder_id
        c["is_folder"] = c.get("mimeType") == "application/vnd.google-apps.folder"
    return children


def list_files_cached(
    google_account: GoogleAccount,
    page_size: int = 100,
    force_refresh: bool = False,
    expand_folders: bool = True,
):
    """Return a short-lived per-account Drive catalog to avoid repeat API calls."""
    cache_key = (
        str(google_account.id or google_account.user_id),
        page_size,
        expand_folders,
    )
    now = time.monotonic()
    ttl = max(settings.DRIVE_FILE_CATALOG_CACHE_TTL_SECONDS, 0)

    if not force_refresh and ttl:
        with _file_catalog_cache_lock:
            cached = _file_catalog_cache.get(cache_key)
            if cached and now - cached[0] < ttl:
                logger.info("[DRIVE] File catalog cache hit for account %s", cache_key)
                return [dict(item) for item in cached[1]]

    files = list_files(
        google_account,
        page_size=page_size,
        expand_folders=expand_folders,
    )
    if ttl:
        with _file_catalog_cache_lock:
            _file_catalog_cache[cache_key] = (
                time.monotonic(),
                [dict(item) for item in files],
            )
            while len(_file_catalog_cache) > 128:
                oldest_key = min(
                    _file_catalog_cache,
                    key=lambda key: _file_catalog_cache[key][0],
                )
                del _file_catalog_cache[oldest_key]
    return files


def get_cached_file_catalog(
    google_account: GoogleAccount,
    page_size: int = 100,
    expand_folders: bool = False,
):
    """Return a fresh in-memory catalog without making a Drive API request."""
    account_id = str(google_account.id or google_account.user_id)
    now = time.monotonic()
    ttl = max(settings.DRIVE_FILE_CATALOG_CACHE_TTL_SECONDS, 0)
    if not ttl:
        return None

    cache_keys = [
        (account_id, page_size, expand_folders),
        (account_id, page_size, True),
    ] if not expand_folders else [(account_id, page_size, True)]

    with _file_catalog_cache_lock:
        for cache_key in cache_keys:
            cached = _file_catalog_cache.get(cache_key)
            if cached and now - cached[0] < ttl:
                return [dict(item) for item in cached[1]]
    return None


def clear_file_catalog_cache(account_id_or_user_id: str = None):
    """Clear in-memory cached Drive catalog for a specific account/user or entirely."""
    with _file_catalog_cache_lock:
        if account_id_or_user_id is None:
            _file_catalog_cache.clear()
            logger.info("[DRIVE] Entire file catalog cache cleared")
        else:
            acc_str = str(account_id_or_user_id)
            keys_to_del = [k for k in _file_catalog_cache if acc_str in str(k[0])]
            for k in keys_to_del:
                _file_catalog_cache.pop(k, None)
            logger.info("[DRIVE] File catalog cache cleared for %s", acc_str)


def download_file(google_account: GoogleAccount, file_id: str, mime_type: str) -> bytes:
    service = get_drive_service(google_account)
    
    # Handle Google Workspace docs (Docs, Sheets, Slides) by exporting them
    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        request = service.files().export_media(fileId=file_id, mimeType="text/csv")
    elif mime_type == "application/vnd.google-apps.presentation":
        request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
    elif mime_type == "application/vnd.google-apps.folder":
        # Folder: list files inside the folder and return text representation
        children = service.files().list(
            q=f"'{file_id}' in parents and trashed = false",
            fields="files(id, name, mimeType, size)",
            pageSize=30
        ).execute().get("files", [])
        child_names = [f.get("name") for f in children]
        folder_text = f"Google Drive Folder containing: {', '.join(child_names) if child_names else 'No files inside'}"
        return folder_text.encode("utf-8")
    else:
        # Standard binary or text files (PDF, image, docx, txt, etc.)
        request = service.files().get_media(fileId=file_id)

    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request, chunksize=2 * 1024 * 1024)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    file_stream.seek(0)
    return file_stream.read()

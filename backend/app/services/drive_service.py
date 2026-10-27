import io
import logging
import threading
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from app.config import settings
from app.models import GoogleAccount

logger = logging.getLogger(__name__)
_file_catalog_cache = {}
_file_catalog_cache_lock = threading.Lock()


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

def list_files(google_account: GoogleAccount, page_size: int = 100, q: str = None):
    service = get_drive_service(google_account)
    query = "trashed = false"
    if q:
        query += f" and ({q})"
        
    results = service.files().list(
        q=query,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, size, webViewLink, createdTime, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    top_items = results.get("files", [])

    all_files = []
    seen_ids = set()

    for item in top_items:
        fid = item.get("id")
        if fid not in seen_ids:
            seen_ids.add(fid)
            all_files.append(item)

        # If it's a folder, also discover files directly inside it
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            try:
                folder_id = item.get("id")
                folder_name = item.get("name")
                children_res = service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="files(id, name, mimeType, size, webViewLink, createdTime, modifiedTime)",
                    pageSize=100
                ).execute()
                for child in children_res.get("files", []):
                    cid = child.get("id")
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        child["folder_name"] = folder_name
                        all_files.append(child)
            except Exception as e:
                print(f"[DRIVE] Error expanding folder {item.get('name')}: {e}")

    return all_files


def list_files_cached(google_account: GoogleAccount, page_size: int = 100):
    """Return a short-lived per-account Drive catalog to avoid repeat API calls."""
    cache_key = (str(google_account.id or google_account.user_id), page_size)
    now = time.monotonic()
    ttl = max(settings.DRIVE_FILE_CATALOG_CACHE_TTL_SECONDS, 0)

    if ttl:
        with _file_catalog_cache_lock:
            cached = _file_catalog_cache.get(cache_key)
            if cached and now - cached[0] < ttl:
                logger.info("[DRIVE] File catalog cache hit for account %s", cache_key)
                return [dict(item) for item in cached[1]]

    files = list_files(google_account, page_size=page_size)
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
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    file_stream.seek(0)
    return file_stream.read()

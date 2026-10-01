"""a7_drive.py - Tác nhân A7: tải kết quả lên Google Drive."""
import re
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from schemas import Job, Status

SCOPES = ["https://www.googleapis.com/auth/drive.file"]   # chỉ đụng file do app tạo


def _service():
    creds = None
    if Path("token.json").exists():
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)    # mở trình duyệt đăng nhập lần đầu
        Path("token.json").write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def _safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\']', "", name).strip()
    return name[:80] or "Khong_ten"


def _get_or_create_folder(svc, name: str, parent: str | None) -> str:
    q = (f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
         f"and trashed = false")
    if parent:
        q += f" and '{parent}' in parents"
    found = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    return svc.files().create(body=meta, fields="id").execute()["id"]


def _upload(svc, path: str, folder_id: str, name: str, mime: str) -> str:
    media = MediaFileUpload(path, mimetype=mime)
    f = svc.files().create(body={"name": name, "parents": [folder_id]},
                           media_body=media, fields="id, webViewLink").execute()
    return f["webViewLink"]


def run(job: Job) -> Job:
    try:
        svc = _service()
        title = _safe(job.title or Path(job.image_path).stem)
        folder = None
        for part in ("Poetry_Pipeline", "Outputs", f"{datetime.now():%Y-%m-%d}", title):
            folder = _get_or_create_folder(svc, part, folder)

        txt = Path("outputs") / f"{job.job_id}_verified.txt"
        txt.write_text(job.verified_text or "", encoding="utf-8")
        job.drive_links["text"] = _upload(svc, str(txt), folder, f"{title}.txt", "text/plain")
        if job.audio_path:
            job.drive_links["audio"] = _upload(svc, job.audio_path, folder,
                                               f"{title}.wav", "audio/wav")
        job.status = Status.DONE
    except Exception as e:
        job.errors.append(f"A7: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job
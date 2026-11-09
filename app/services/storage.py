"""Saving uploads to disk with size limits and content sniffing. Files get random names; originals are never trusted."""

import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.security import sniff_audio, sniff_image, sniff_scan

CHUNK = 1024 * 1024
BUCKETS = ("memories", "recordings")


@dataclass
class StoredFile:
    relative_path: str   # e.g. "memories/3f9c...e1.jpg", relative to the uploads dir
    mime_type: str
    size: int


def _reject(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


def save_upload(upload: UploadFile, uploads_dir: Path, bucket: str, kind: str, max_mb: int) -> StoredFile:
    """kind: 'image' | 'audio' | 'scan'."""
    head = upload.file.read(64)
    upload.file.seek(0)
    filename = upload.filename or ""
    if kind == "image":
        sniffed = sniff_image(head)
        if not sniffed:
            raise _reject("Please upload a JPEG, PNG or WebP photo (HEIC photos can be exported as JPEG).")
        mime, ext = sniffed
    elif kind == "audio":
        sniffed = sniff_audio(head, filename)
        if not sniffed:
            raise _reject("Unsupported audio format. Use MP3, M4A, WAV, OGG, FLAC or record in the browser.")
        mime, ext = sniffed
    elif kind == "video":
        if head[4:8] == b"ftyp" and filename.lower().endswith(".mp4"):
            mime, ext = "video/mp4", ".mp4"
        elif head.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in head.lower() and filename.lower().endswith(".webm"):
            mime, ext = "video/webm", ".webm"
        else:
            raise _reject("Please upload an MP4 or WebM video.")
    elif kind == "scan":
        ext = sniff_scan(head, filename)
        if not ext:
            raise _reject("Unsupported 3D scan. Upload a Gaussian splat as .ply, .spz, .splat, .ksplat or .sog.")
        mime = "application/octet-stream"
    else:
        raise ValueError(kind)

    target_dir = uploads_dir / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}{ext}"
    target = target_dir / name
    limit = max_mb * CHUNK
    size = 0
    try:
        with target.open("wb") as out:
            while chunk := upload.file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise _reject(f"The file is larger than {max_mb} MB.")
                out.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if size == 0:
        target.unlink(missing_ok=True)
        raise _reject("The uploaded file is empty.")
    return StoredFile(relative_path=f"{bucket}/{name}", mime_type=mime, size=size)


def resolve_upload(uploads_dir: Path, bucket: str, filename: str) -> Path | None:
    """Map a public URL segment back to a file, refusing anything that is not a plain generated name."""
    if bucket not in BUCKETS or "/" in filename or "\\" in filename or filename.startswith("."):
        return None
    path = (uploads_dir / bucket / filename).resolve()
    if path.parent != (uploads_dir / bucket).resolve() or not path.is_file():
        return None
    return path


def write_bytes(uploads_dir: Path, bucket: str, data: bytes, ext: str) -> str:
    target_dir = uploads_dir / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}{ext}"
    (target_dir / name).write_bytes(data)
    return f"{bucket}/{name}"

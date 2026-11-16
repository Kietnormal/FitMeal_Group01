import base64
import hashlib
import io
import os
from datetime import datetime
from pathlib import Path
import shutil
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

BACKUP_PREFIX = "fitmeal-"
BACKUP_SUFFIX = ".json.enc"
BACKUP_RETENTION_COUNT = 14


def _backup_cipher():
    key_material = settings.BACKUP_ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def backup_root():
    return Path(settings.BACKUP_ROOT).resolve()


def create_database_backup():
    output = io.StringIO()
    call_command(
        "dumpdata",
        exclude=["contenttypes", "sessions"],
        natural_foreign=True,
        natural_primary=True,
        stdout=output,
    )
    encrypted = _backup_cipher().encrypt(output.getvalue().encode("utf-8"))
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{BACKUP_PREFIX}{timezone.localtime().strftime('%Y%m%d-%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}{BACKUP_SUFFIX}"
    )
    destination = root / filename
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_bytes(encrypted)
        os.replace(temporary, destination)
        if settings.BACKUP_EXTERNAL_ROOT:
            external_root = Path(settings.BACKUP_EXTERNAL_ROOT).resolve()
            if external_root == root:
                raise ValueError("Kho backup ngoài phải khác thư mục backup nội bộ.")
            external_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, external_root / filename)
    finally:
        if temporary.exists():
            temporary.unlink()
    backups = sorted(
        root.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[BACKUP_RETENTION_COUNT:]:
        old_backup.unlink()
    return destination


def list_database_backups():
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(
        (
            {
                "filename": path.name,
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=timezone.get_current_timezone(),
                ),
                "modified_timestamp": path.stat().st_mtime,
            }
            for path in root.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
            if path.is_file()
        ),
        key=lambda backup: backup["modified_timestamp"],
        reverse=True,
    )


def get_database_backup(filename):
    if (
        not filename.startswith(BACKUP_PREFIX)
        or not filename.endswith(BACKUP_SUFFIX)
        or Path(filename).name != filename
    ):
        return None
    path = backup_root() / filename
    return path if path.is_file() else None

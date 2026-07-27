import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.document_parser import PARSER_REGISTRY, SUPPORTED_PARSE_EXTS


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_TEXT_CHARS = 120_000
DEFAULT_ATTACHMENT_TTL_MINUTES = 60


@dataclass(frozen=True)
class TemporaryAttachment:
    id: str
    filename: str
    content_type: str
    size: int
    path: str
    status: str
    created_at: str
    expires_at: str
    consumed_at: str = ""
    parse_error: str = ""
    text_path: str = ""

    def to_response(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        data.pop("text_path", None)
        data["parse_error"] = data["parse_error"] or None
        return data


class TemporaryAttachmentRepository:
    def __init__(
        self,
        root_dir: Path | str,
        *,
        ttl_minutes: int = DEFAULT_ATTACHMENT_TTL_MINUTES,
        max_bytes: int = MAX_ATTACHMENT_BYTES,
        max_text_chars: int = MAX_ATTACHMENT_TEXT_CHARS,
    ):
        self.root_dir = Path(root_dir)
        self.ttl = timedelta(minutes=max(1, int(ttl_minutes)))
        self.max_bytes = max(1024, int(max_bytes))
        self.max_text_chars = max(1000, int(max_text_chars))
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @property
    def supported_extensions(self) -> set[str]:
        return set(SUPPORTED_PARSE_EXTS)

    def cleanup_expired(self) -> int:
        now = datetime.now()
        removed = 0
        for meta_path in self.root_dir.glob("*/metadata.json"):
            try:
                item = self._read_metadata(meta_path)
                if self._is_expired(item, now):
                    shutil.rmtree(meta_path.parent, ignore_errors=True)
                    removed += 1
            except Exception:
                continue
        return removed

    def create(self, filename: str, content: bytes, content_type: str = "") -> TemporaryAttachment:
        safe_name = self._safe_filename(filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in self.supported_extensions:
            raise ValueError(f"Unsupported temporary attachment type: {suffix or '(none)'}")
        if not content:
            raise ValueError("Temporary attachment is empty")
        if len(content) > self.max_bytes:
            raise ValueError(f"Temporary attachment exceeds {self.max_bytes} bytes")

        self.root_dir.mkdir(parents=True, exist_ok=True)
        attachment_id = f"att_{uuid.uuid4().hex}"
        item_dir = self.root_dir / attachment_id
        item_dir.mkdir(parents=False, exist_ok=False)
        file_path = item_dir / safe_name
        file_path.write_bytes(content)
        text_path = item_dir / "extracted.txt"
        now = datetime.now()

        status = "parsed"
        parse_error = ""
        try:
            parsed = PARSER_REGISTRY.parse(file_path, engine="builtin")
            extracted_text = (parsed.markdown or "\n\n".join(element.text for element in parsed.elements)).strip()
            extracted_text = extracted_text[: self.max_text_chars]
            if not extracted_text:
                raise ValueError("No readable text extracted")
            text_path.write_text(extracted_text, encoding="utf-8")
        except Exception as exc:
            status = "failed"
            parse_error = str(exc)

        attachment = TemporaryAttachment(
            id=attachment_id,
            filename=safe_name,
            content_type=content_type,
            size=len(content),
            path=str(file_path),
            status=status,
            created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + self.ttl).isoformat(timespec="seconds"),
            parse_error=parse_error,
            text_path=str(text_path) if text_path.exists() else "",
        )
        self._write_metadata(item_dir / "metadata.json", attachment)
        if status == "failed":
            raise ValueError(f"Failed to parse temporary attachment: {parse_error}")
        return attachment

    def resolve_many(self, attachment_ids: list[str] | tuple[str, ...] | None) -> list[dict[str, Any]]:
        ids = [str(item).strip() for item in (attachment_ids or []) if str(item).strip()]
        if len(ids) > 5:
            raise ValueError("A chat request can include at most 5 temporary attachments")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate temporary attachment ids are not allowed")
        self.cleanup_expired()
        return [self.resolve(item) for item in ids]

    def resolve(self, attachment_id: str) -> dict[str, Any]:
        item_dir = self._attachment_dir(attachment_id)
        meta_path = item_dir / "metadata.json"
        if not meta_path.exists():
            raise ValueError(f"Temporary attachment not found or expired: {attachment_id}")
        attachment = self._read_metadata(meta_path)
        if self._is_expired(attachment):
            shutil.rmtree(item_dir, ignore_errors=True)
            raise ValueError(f"Temporary attachment not found or expired: {attachment_id}")
        if attachment.status != "parsed" or not attachment.text_path:
            raise ValueError(f"Temporary attachment is not ready: {attachment.filename}")
        text_path = Path(attachment.text_path).resolve()
        try:
            text_path.relative_to(item_dir)
        except ValueError as exc:
            raise ValueError("Temporary attachment path is invalid") from exc
        text = text_path.read_text(encoding="utf-8")[: self.max_text_chars]
        return {
            "id": attachment.id,
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size": attachment.size,
            "text": text,
            "source": self.source_for(attachment),
        }

    def mark_consumed(self, attachment_ids: list[str] | tuple[str, ...] | None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        for attachment_id in attachment_ids or []:
            meta_path = self._attachment_dir(str(attachment_id)) / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                attachment = self._read_metadata(meta_path)
                updated = TemporaryAttachment(**{**asdict(attachment), "consumed_at": now})
                self._write_metadata(meta_path, updated)
            except Exception:
                continue

    def source_for(self, attachment: TemporaryAttachment) -> dict[str, Any]:
        return {
            "source": f"临时附件: {attachment.filename}",
            "score": 1.0,
            "doc_id": attachment.id,
            "chunk_id": "",
            "parent_id": "",
            "title_path": "",
            "workspace_id": "",
            "knowledge_base_id": "",
            "source_type": "temporary_attachment",
            "temporary_attachment_id": attachment.id,
            "filename": attachment.filename,
        }

    def source_for_resolved(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": f"临时附件: {item['filename']}",
            "score": 1.0,
            "doc_id": item["id"],
            "chunk_id": "",
            "parent_id": "",
            "title_path": "",
            "workspace_id": "",
            "knowledge_base_id": "",
            "source_type": "temporary_attachment",
            "temporary_attachment_id": item["id"],
            "filename": item["filename"],
        }

    def _attachment_dir(self, attachment_id: str) -> Path:
        if not attachment_id.startswith("att_") or any(char in attachment_id for char in "\\/.:"):
            raise ValueError("Invalid temporary attachment id")
        path = self.root_dir / attachment_id
        resolved_root = self.root_dir.resolve()
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("Invalid temporary attachment path") from exc
        return resolved_path

    def _safe_filename(self, filename: str) -> str:
        name = Path(filename or "attachment").name.strip()
        name = "".join(char for char in name if char not in "\\/:*?\"<>|").strip(" .")
        if not name:
            name = "attachment"
        return name[:160]

    def _read_metadata(self, path: Path) -> TemporaryAttachment:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TemporaryAttachment(**data)

    def _write_metadata(self, path: Path, attachment: TemporaryAttachment) -> None:
        path.write_text(json.dumps(asdict(attachment), ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_expired(self, attachment: TemporaryAttachment, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        try:
            return datetime.fromisoformat(attachment.expires_at) <= now
        except ValueError:
            return True

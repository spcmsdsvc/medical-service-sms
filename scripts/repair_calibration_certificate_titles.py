"""Repair stale approver titles on current signed Calibration Certificates.

The command is deliberately dry-run by default.  Applying a repair requires a
repeatable explicit ``--approval-id``, a matching ``--expected-count``, and the
``--apply`` switch.  Only current/latest Approved certificates assigned to the
Robert (``robert``) or Rodito (``rodito``) accounts are considered.

The signed PDF is regenerated from the approval's immutable mapped snapshot and
stored approval identity.  The existing signed ``ShiftFile`` object is replaced
in place after a verified backup; approval linkage, revision, certificate number,
submission, and the no-signature copy are not rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import sys
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence


ALLOWED_APPROVERS = ("robert", "rodito")
DEFAULT_APPROVERS = list(ALLOWED_APPROVERS)
REPORTS_PREFIX = "reports"
BACKUP_DIRECTORY = "_calibration_certificate_title_repair_backups"
AUDIT_ACTION = "title_repaired"
DIVISION_TEXT = "Medical Systems Division"
CERTIFICATE_FIELDS = (
    "Textfield",
    "Text1",
    "Text2",
    "Text3",
    "Text4",
    "Text5",
    "Text6",
    "Textfield-0",
)


class RepairError(RuntimeError):
    """A selected record cannot be safely inspected or repaired."""


class RepairGuardError(RepairError):
    """The command was invoked without the required explicit apply guard."""


class RepairStaleError(RepairError):
    """A record changed after inspection and must be reviewed again."""


class _SystemActor:
    is_authenticated = False


SYSTEM_ACTOR = _SystemActor()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _username(user: Any) -> str:
    return _text(getattr(user, "username", "")).casefold()


def _normalize_title(value: Any) -> str:
    """Normalize a title while treating the fixed division line as structural."""
    text = re.sub(r"\s+", " ", _text(value)).strip()
    text = re.sub(
        r"(?i)[\s,;:\-–—]*medical\s+systems\s+division\s*$",
        "",
        text,
    )
    return text.strip(" \t\r\n,;:\-–—").casefold()


def _display_title(value: Any) -> str:
    text = re.sub(r"\s+", " ", _text(value)).strip()
    text = re.sub(
        r"(?i)[\s,;:\-–—]*medical\s+systems\s+division\s*$",
        "",
        text,
    )
    return text.strip(" \t\r\n,;:\-–—")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approver",
        dest="approvers",
        action="append",
        metavar="USERNAME",
        help="Limit inspection to robert or rodito; repeat for both.",
    )
    parser.add_argument(
        "--approval-id",
        dest="approval_ids",
        action="append",
        type=int,
        metavar="ID",
        help="Explicit approval id; repeat once per selected certificate.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        help="Required with --apply; must equal the number of explicit approval ids.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write verified backups, replacement PDFs, metadata, and audit events.",
    )
    args = parser.parse_args(argv)
    raw_approvers = args.approvers or list(DEFAULT_APPROVERS)
    args.approvers = []
    for value in raw_approvers:
        normalized = _text(value).casefold()
        if normalized not in ALLOWED_APPROVERS:
            parser.error("--approver must be robert or rodito")
        if normalized not in args.approvers:
            args.approvers.append(normalized)
    if args.approval_ids is not None:
        if any(value <= 0 for value in args.approval_ids):
            parser.error("--approval-id values must be positive integers")
        if len(set(args.approval_ids)) != len(args.approval_ids):
            parser.error("--approval-id values must be unique")
    if args.expected_count is not None and args.expected_count < 0:
        parser.error("--expected-count must be zero or greater")
    return args


def _validation(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _file_name(app_module: Any, file_record: Any) -> str:
    display = getattr(app_module, "get_shift_file_display_name", None)
    if callable(display):
        try:
            value = display(file_record)
            if _text(value):
                return _text(value)
        except Exception:
            pass
    return _text(getattr(file_record, "original_filename", "")) or _text(
        getattr(file_record, "filename", "")
    )


def _file_disk_name(app_module: Any, file_record: Any) -> str:
    resolver = getattr(app_module, "get_shift_file_disk_name", None)
    if callable(resolver):
        try:
            value = _text(resolver(file_record))
            if value:
                return value
        except Exception:
            pass
    return _text(getattr(file_record, "filename", ""))


def _approval_user(app_module: Any, approval: Any) -> Any:
    user = getattr(approval, "approver", None)
    user_id = getattr(approval, "approver_user_id", None)
    if user is None and user_id:
        model = getattr(app_module, "User", None)
        session = getattr(getattr(app_module, "db", None), "session", None)
        getter = getattr(session, "get", None)
        if callable(getter) and model is not None:
            user = getter(model, user_id)
    return user


def _submission_for_approval(app_module: Any, approval: Any) -> Any:
    submission = getattr(approval, "online_tsr_submission", None)
    if submission is not None:
        return submission
    submission_id = getattr(approval, "online_tsr_submission_id", None)
    model = getattr(app_module, "OnlineTsrSubmission", None)
    session = getattr(getattr(app_module, "db", None), "session", None)
    getter = getattr(session, "get", None)
    return getter(model, submission_id) if callable(getter) and model is not None and submission_id else None


def _signed_file_for_approval(app_module: Any, approval: Any) -> Any:
    file_record = getattr(approval, "signed_shift_file", None)
    file_id = getattr(approval, "signed_shift_file_id", None)
    model = getattr(app_module, "ShiftFile", None)
    session = getattr(getattr(app_module, "db", None), "session", None)
    getter = getattr(session, "get", None)
    if file_record is None and callable(getter) and model is not None and file_id:
        file_record = getter(model, file_id)
    return file_record


def _local_path(app_module: Any, file_record: Any) -> str:
    disk_name = _file_disk_name(app_module, file_record)
    if not disk_name:
        raise RepairError("The signed certificate has no stored filename.")
    upload_folder = _text(getattr(app_module, "app", None).config.get("UPLOAD_FOLDER"))
    if not upload_folder:
        raise RepairError("The application upload folder is not configured.")
    return os.path.join(upload_folder, os.path.basename(disk_name))


def _read_storage_bytes(app_module: Any, prefix: str, local_path: str) -> bytes:
    reader = getattr(app_module, "managed_storage_read_path", None)
    readable_path = None
    if callable(reader):
        readable_path = reader(prefix, local_path)
    else:
        readable_path = local_path
    try:
        with open(readable_path, "rb") as file_handle:
            return file_handle.read()
    finally:
        release = getattr(app_module, "managed_storage_release_path", None)
        if callable(release) and readable_path and readable_path != local_path:
            release(readable_path)


def _read_signed_certificate_bytes(app_module: Any, approval: Any, file_record: Any | None = None) -> bytes:
    file_record = file_record or _signed_file_for_approval(app_module, approval)
    if not file_record:
        raise RepairError("The signed Calibration Certificate is unavailable.")
    return _read_storage_bytes(
        app_module,
        _text(getattr(app_module, "STORAGE_PREFIX_REPORTS", REPORTS_PREFIX)) or REPORTS_PREFIX,
        _local_path(app_module, file_record),
    )


def _pdf_text(pdf_bytes: bytes) -> tuple[Any, str]:
    try:
        from pypdf import PdfReader
    except Exception as dependency_error:  # pragma: no cover - environment failure
        raise RepairError(f"pypdf is required for certificate repair: {dependency_error}") from dependency_error
    try:
        reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as pdf_error:
        raise RepairError(f"The signed certificate PDF could not be read: {pdf_error}") from pdf_error
    return reader, text


def _fitz_spans(pdf_bytes: bytes) -> tuple[list[dict[str, Any]], int, int]:
    try:
        import fitz
    except Exception as dependency_error:  # pragma: no cover - environment failure
        raise RepairError(f"PyMuPDF is required for certificate repair: {dependency_error}") from dependency_error
    try:
        document = fitz.open(stream=bytes(pdf_bytes), filetype="pdf")
        if not document.page_count:
            raise RepairError("The certificate PDF contains no pages.")
        page = document[0]
        spans: list[dict[str, Any]] = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = _text(span.get("text"))
                    if text:
                        spans.append({
                            "text": text,
                            "x0": float(span.get("bbox", (0, 0, 0, 0))[0]),
                            "y0": float(span.get("bbox", (0, 0, 0, 0))[1]),
                            "x1": float(span.get("bbox", (0, 0, 0, 0))[2]),
                            "y1": float(span.get("bbox", (0, 0, 0, 0))[3]),
                        })
        return spans, int(document.page_count), len(page.get_images(full=True))
    except RepairError:
        raise
    except Exception as pdf_error:
        raise RepairError(f"PyMuPDF could not inspect the certificate PDF: {pdf_error}") from pdf_error


def extract_rendered_title(pdf_bytes: bytes, expected_name: str) -> str:
    """Extract only the rendered title in the approver block.

    PyMuPDF coordinates are used instead of relying on pypdf's content-stream
    order, which varies when a title and name use different embedded fonts.
    The fixed division line is structural and is intentionally omitted from the
    returned title.
    """
    expected_name = _text(expected_name)
    if not expected_name:
        raise RepairError("The stored approver name snapshot is blank.")
    _, text = _pdf_text(pdf_bytes)
    spans, _, _ = _fitz_spans(pdf_bytes)
    expected_key = re.sub(r"\s+", " ", expected_name).casefold()
    name_spans = [
        span for span in spans
        if re.sub(r"\s+", " ", span["text"]).casefold() == expected_key
    ]
    # The certifier block is on the lower-right of the one-page Letter form.
    # Keep a broad region to tolerate small template/font geometry changes while
    # avoiding the footer's unrelated text.
    region = [
        span for span in spans
        if span["x1"] >= 380 and span["x0"] <= 540 and 500 <= span["y0"] <= 610
    ]
    division_spans = [
        span for span in region
        if re.sub(r"\s+", " ", span["text"]).casefold() == DIVISION_TEXT.casefold()
    ]
    if name_spans and division_spans:
        name_y = min(span["y0"] for span in name_spans)
        division_y = min(
            span["y0"] for span in division_spans if span["y0"] > name_y
        ) if any(span["y0"] > name_y for span in division_spans) else None
        if division_y is not None:
            title_spans = [
                span for span in region
                if span["y0"] > name_y + 0.25
                and span["y0"] < division_y - 0.25
                and re.sub(r"\s+", " ", span["text"]).casefold() not in {
                    expected_key,
                    DIVISION_TEXT.casefold(),
                }
            ]
            title_spans.sort(key=lambda span: (span["y0"], span["x0"]))
            title = " ".join(span["text"] for span in title_spans)
            if title:
                return _display_title(title)

    # Conservative fallback for environments where PyMuPDF emits no usable
    # span coordinates.  It still requires the stored name and division text.
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    name_index = next(
        (index for index, line in enumerate(lines) if line.casefold() == expected_key),
        None,
    )
    division_index = next(
        (index for index, line in enumerate(lines) if line.casefold() == DIVISION_TEXT.casefold()),
        None,
    )
    if name_index is None or division_index is None:
        raise RepairError("The signed certificate approver block is missing the stored name or division.")
    between = []
    if division_index > name_index:
        between = lines[name_index + 1:division_index]
    if not between and name_index > 0:
        between = lines[max(0, name_index - 2):name_index]
    ignored = {
        expected_key,
        "certified by:",
        "disclaimer",
        ":",
    }
    title_lines = [line for line in between if line.casefold() not in ignored]
    if not title_lines:
        raise RepairError("The signed certificate approver title is missing.")
    return _display_title(" ".join(title_lines))


def _page_has_no_annotations(page: Any) -> bool:
    annotations = page.get("/Annots")
    if annotations is None:
        return True
    try:
        return len(annotations.get_object() if hasattr(annotations, "get_object") else annotations) == 0
    except Exception:
        return False


def verify_regenerated_certificate(
    pdf_bytes: bytes,
    *,
    mapped_values: Mapping[str, Any],
    approver_name: str,
    approval_title: str,
    signature_data: str = "",
) -> dict[str, Any]:
    """Verify the static, flattened, one-page certificate contract."""
    reader, extracted = _pdf_text(pdf_bytes)
    if len(reader.pages) != 1:
        raise RepairError("The regenerated certificate must contain exactly one page.")
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if abs(width - 612) > 0.1 or abs(height - 792) > 0.1:
        raise RepairError("The regenerated certificate must be Letter size (612 x 792 points).")
    if reader.get_fields() or not _page_has_no_annotations(page):
        raise RepairError("The regenerated certificate must contain no fields or annotations.")
    normalized_text = re.sub(r"\s+", " ", extracted).strip()
    for field_name in CERTIFICATE_FIELDS:
        value = _text(mapped_values.get(field_name))
        if value and value not in extracted and re.sub(r"\s+", " ", value) not in normalized_text:
            raise RepairError(f"The regenerated certificate is missing mapped value {field_name}.")
    if _text(approver_name) not in extracted:
        raise RepairError("The regenerated certificate is missing the stored approver name.")
    division_count = normalized_text.count(DIVISION_TEXT)
    if division_count != 1:
        raise RepairError(
            f"The regenerated certificate must contain exactly one {DIVISION_TEXT}; found {division_count}."
        )
    if "superadmin" in normalized_text.casefold():
        raise RepairError("The regenerated certificate contains stale Superadmin text.")
    rendered_title = extract_rendered_title(pdf_bytes, expected_name=approver_name)
    if _normalize_title(rendered_title) != _normalize_title(approval_title):
        raise RepairError(
            f"The regenerated certificate title {rendered_title!r} does not match {approval_title!r}."
        )
    spans, page_count, image_count = _fitz_spans(pdf_bytes)
    if page_count != 1:
        raise RepairError("PyMuPDF did not confirm one certificate page.")
    if signature_data and image_count < 1:
        raise RepairError("The regenerated certificate does not contain the stored signature image.")
    return {
        "sha256": hashlib.sha256(bytes(pdf_bytes)).hexdigest(),
        "page_count": 1,
        "width": width,
        "height": height,
        "division_count": division_count,
        "rendered_title": rendered_title,
        "image_count": image_count,
        "span_count": len(spans),
    }


def inspect_approval(
    app_module: Any,
    approval: Any,
    *,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Inspect one approval and return a JSON-safe dry-run row."""
    user = _approval_user(app_module, approval)
    username = _username(user)
    current_title = _text(getattr(user, "approval_title", ""))
    stored_title = _text(getattr(approval, "approver_title_snapshot", ""))
    stored_name = _text(getattr(approval, "approver_name_snapshot", ""))
    file_record = _signed_file_for_approval(app_module, approval)
    submission = _submission_for_approval(app_module, approval)
    row: dict[str, Any] = {
        "approval_id": getattr(approval, "id", None),
        "certificate_number": _text(getattr(approval, "certificate_number", "")),
        "approver_username": username,
        "approver_user_id": getattr(approval, "approver_user_id", None),
        "approver_name_snapshot": stored_name,
        "approver_signature_snapshot_sha256": hashlib.sha256(
            _text(getattr(approval, "approver_signature_snapshot", "")).encode("utf-8")
        ).hexdigest(),
        "signed_filename": _file_name(app_module, file_record) if file_record else "",
        "shift_id": getattr(approval, "shift_id", None),
        "submission_id": getattr(approval, "online_tsr_submission_id", None),
        "signed_shift_file_id": getattr(approval, "signed_shift_file_id", None),
        "no_signature_shift_file_id": getattr(approval, "no_signature_shift_file_id", None),
        "revision_no": getattr(approval, "revision_no", None),
        "current_title": current_title,
        "stored_title": stored_title,
        "rendered_title": "",
        "stored_title_mismatch": False,
        "rendered_title_mismatch": False,
        "old_sha256": "",
        "new_sha256": "",
        "eligible": False,
        "reason": "",
        "validations": [],
    }
    structural_ok = True

    status_ok = _text(getattr(approval, "status", "")) == "Approved"
    latest_ok = bool(getattr(approval, "is_latest", False))
    row["validations"].append(_validation("status_approved", status_ok, getattr(approval, "status", "")))
    row["validations"].append(_validation("latest_revision", latest_ok, str(getattr(approval, "is_latest", False))))
    if not status_ok or not latest_ok:
        row["reason"] = "not-current-approved"
        return row

    approver_ok = username in ALLOWED_APPROVERS
    selected_link_ok = bool(
        user and getattr(user, "id", None) == getattr(approval, "approver_user_id", None)
    )
    title_ok = bool(current_title)
    name_ok = bool(stored_name)
    row["validations"].extend([
        _validation("approver_username_allowed", approver_ok, username),
        _validation("approver_linked", selected_link_ok, str(getattr(approval, "approver_user_id", ""))),
        _validation("current_title_nonblank", title_ok, current_title),
        _validation("stored_name_nonblank", name_ok, stored_name),
    ])
    if not approver_ok:
        row["reason"] = "approver-not-allowed"
        return row
    if not selected_link_ok:
        row["reason"] = "approver-linkage-mismatch"
        return row
    if not title_ok:
        row["reason"] = "current-title-blank"
        return row
    if not name_ok:
        row["reason"] = "stored-approver-name-blank"
        return row

    linkage_ok = bool(
        file_record
        and getattr(file_record, "id", None) == getattr(approval, "signed_shift_file_id", None)
        and getattr(file_record, "shift_id", None) == getattr(approval, "shift_id", None)
        and getattr(file_record, "online_tsr_submission_id", None) == getattr(approval, "online_tsr_submission_id", None)
        and _file_name(app_module, file_record).casefold().endswith(".pdf")
    )
    submission_link_ok = bool(
        submission
        and getattr(submission, "id", None) == getattr(approval, "online_tsr_submission_id", None)
        and getattr(submission, "shift_id", None) == getattr(approval, "shift_id", None)
    )
    row["validations"].extend([
        _validation("signed_file_linkage", linkage_ok, str(getattr(file_record, "id", ""))),
        _validation("submission_linkage", submission_link_ok, str(getattr(submission, "id", ""))),
    ])
    structural_ok = linkage_ok and submission_link_ok
    if not structural_ok:
        row["reason"] = "signed-file-or-submission-linkage-mismatch"
        return row

    try:
        if source_bytes is None:
            source_bytes = _read_signed_certificate_bytes(app_module, approval, file_record)
        row["old_sha256"] = hashlib.sha256(bytes(source_bytes)).hexdigest()
        row["validations"].append(_validation("source_readable", bool(source_bytes), row["old_sha256"]))
        stored_fingerprint = _text(getattr(approval, "certificate_fingerprint", ""))
        fingerprint_ok = not stored_fingerprint or stored_fingerprint.casefold() == row["old_sha256"].casefold()
        row["validations"].append(_validation("stored_fingerprint_matches_source", fingerprint_ok, stored_fingerprint))
        if not fingerprint_ok:
            row["reason"] = "stored-fingerprint-mismatch"
            return row
        rendered_title = extract_rendered_title(source_bytes, expected_name=stored_name)
        row["rendered_title"] = rendered_title
        row["validations"].append(_validation("rendered_title_readable", True, rendered_title))
    except Exception as read_error:
        row["validations"].append(_validation("rendered_title_readable", False, str(read_error)))
        row["reason"] = "signed-pdf-title-unreadable"
        return row

    # The snapshot is a database value and must converge to the exact current
    # User.approval_title string.  Rendered comparison remains division-aware
    # because the builder draws that fixed line separately.
    row["stored_title_mismatch"] = stored_title != current_title
    row["rendered_title_mismatch"] = _normalize_title(row["rendered_title"]) != _normalize_title(current_title)
    row["validations"].extend([
        _validation("stored_title_matches_current", not row["stored_title_mismatch"], stored_title),
        _validation("rendered_title_matches_current", not row["rendered_title_mismatch"], row["rendered_title"]),
    ])
    if not row["stored_title_mismatch"] and not row["rendered_title_mismatch"]:
        row["reason"] = "already-current"
        return row
    row["eligible"] = True
    row["reason"] = "title-stale"
    return row


def _collect_approval_rows(
    app_module: Any,
    approvers: Sequence[str],
    approval_ids: Sequence[int] | None,
    *,
    ensure_schema: bool = True,
) -> list[Any]:
    ensure = getattr(app_module, "ensure_calibration_certificate_approval_table", None)
    if ensure_schema and callable(ensure):
        ensure()
    if approval_ids:
        model = getattr(app_module, "CalibrationCertificateApproval", None)
        session = getattr(getattr(app_module, "db", None), "session", None)
        getter = getattr(session, "get", None)
        return [getter(model, approval_id) if callable(getter) and model is not None else None for approval_id in approval_ids]
    model = getattr(app_module, "CalibrationCertificateApproval", None)
    query = getattr(model, "query", None)
    if query is None:
        return []
    try:
        query = query.filter(model.status == "Approved", model.is_latest.is_(True))
    except Exception:
        pass
    try:
        query = query.order_by(model.approved_at.desc(), model.id.desc())
    except Exception:
        pass
    all_rows = query.all() if hasattr(query, "all") else list(query)
    return [row for row in all_rows if _username(_approval_user(app_module, row)) in set(approvers)]


def _payload_for_approval(app_module: Any, approval: Any) -> dict[str, Any]:
    submission = _submission_for_approval(app_module, approval)
    if not submission:
        raise RepairError("The approval's TSR submission is unavailable.")
    parser = getattr(app_module, "parse_online_tsr_payload_json", None)
    payload = parser(submission) if callable(parser) else json.loads(getattr(submission, "payload_json", "{}") or "{}")
    if not isinstance(payload, dict):
        raise RepairError("The approval's TSR payload is not an object.")
    return payload


def _prepare_repair(app_module: Any, approval: Any, inspection: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_loader = getattr(app_module, "calibration_certificate_mapped_snapshot", None)
    mapped_values = snapshot_loader(getattr(approval, "mapped_data_json", "{}")) if callable(snapshot_loader) else None
    if not isinstance(mapped_values, dict) or any(not _text(mapped_values.get(field)) for field in CERTIFICATE_FIELDS):
        raise RepairError("The immutable mapped certificate snapshot is incomplete.")
    stored_name = _text(getattr(approval, "approver_name_snapshot", ""))
    signature_data = _text(getattr(approval, "approver_signature_snapshot", ""))
    current_title = _text(inspection.get("current_title"))
    if not stored_name or not current_title:
        raise RepairError("The stored approver identity or current title is blank.")
    builder = getattr(app_module, "build_calibration_certificate_pdf", None)
    if not callable(builder):
        raise RepairError("The application certificate builder is unavailable.")
    payload = _payload_for_approval(app_module, approval)
    new_bytes, returned_values, builder_fingerprint = builder(
        payload,
        shift=None,
        approver=stored_name,
        signature_data=signature_data,
        approval_title=current_title,
        certificate_number_override=getattr(approval, "certificate_number", ""),
        mapped_values_override=mapped_values,
    )
    verification = verify_regenerated_certificate(
        new_bytes,
        mapped_values=returned_values or mapped_values,
        approver_name=stored_name,
        approval_title=current_title,
        signature_data=signature_data,
    )
    new_sha256 = verification["sha256"]
    if builder_fingerprint and _text(builder_fingerprint).casefold() != new_sha256.casefold():
        raise RepairError("The certificate builder fingerprint does not match the generated bytes.")
    return {
        "bytes": bytes(new_bytes),
        "mapped_values": returned_values or mapped_values,
        "verification": verification,
        "new_sha256": new_sha256,
    }


def _real_storage_write_bytes(
    app_module: Any,
    prefix: str,
    local_path: str,
    data: bytes,
    *,
    original_filename: str,
    purpose: str,
) -> dict[str, Any]:
    """Write one object without registering it in the app rollback hook.

    This command overwrites an existing object deliberately.  The request-level
    ``managed_storage_write_bytes`` helper registers paths as newly-created and
    would delete the restored/original object during a later SQLAlchemy rollback.
    Direct adapter writes keep backup and replacement rollback under this command's
    explicit control.
    """
    storage = getattr(app_module, "file_storage", None)
    if storage is None:
        writer = getattr(app_module, "managed_storage_write_bytes", None)
        if not callable(writer):
            raise RepairError("Managed storage writer is unavailable.")
        return writer(prefix, local_path, data, original_filename=original_filename, content_type="application/pdf")
    key_builder = getattr(app_module, "managed_storage_key", None)
    key = key_builder(prefix, local_path) if callable(key_builder) else storage.normalize_key(
        f"{prefix}/{os.path.basename(local_path)}"
    )
    bucket_written = False
    if bool(getattr(storage, "writes_bucket", False)):
        storage.upload_bytes(
            key,
            bytes(data),
            content_type="application/pdf",
            original_filename=original_filename or os.path.basename(local_path),
            extra_metadata={"repair-purpose": purpose},
        )
        bucket_written = True
    volume_written = False
    if bool(getattr(storage, "writes_volume", False)):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        temporary_path = f"{local_path}.title-repairing-{secrets.token_hex(6)}"
        try:
            with open(temporary_path, "wb") as target:
                target.write(bytes(data))
            os.replace(temporary_path, local_path)
            volume_written = True
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
    return {
        "key": key,
        "size": len(data),
        "bucket_written": bucket_written,
        "volume_written": volume_written,
        "purpose": purpose,
    }


def _storage_write_bytes(
    app_module: Any,
    prefix: str,
    local_path: str,
    data: bytes,
    *,
    original_filename: str,
    purpose: str,
) -> dict[str, Any]:
    return _real_storage_write_bytes(
        app_module,
        prefix,
        local_path,
        data,
        original_filename=original_filename,
        purpose=purpose,
    )


def _backup_original(
    app_module: Any,
    approval_id: Any,
    target_path: str,
    original_bytes: bytes,
    original_filename: str,
) -> dict[str, Any]:
    old_sha256 = hashlib.sha256(bytes(original_bytes)).hexdigest()
    today_fn = getattr(app_module, "get_manila_today", None)
    backup_date = today_fn() if callable(today_fn) else date.today()
    date_text = backup_date.isoformat() if hasattr(backup_date, "isoformat") else _text(backup_date)
    file_id = os.path.basename(target_path).split("_", 1)[0] or "file"
    backup_name = f"approval_{approval_id}_{file_id}_{old_sha256[:16]}.pdf"
    upload_folder = _text(getattr(app_module, "app", None).config.get("UPLOAD_FOLDER"))
    backup_path = os.path.join(upload_folder, BACKUP_DIRECTORY, date_text, backup_name)
    prefix_root = _text(getattr(app_module, "STORAGE_PREFIX_REPORTS", REPORTS_PREFIX)) or REPORTS_PREFIX
    backup_prefix = f"{prefix_root}/{BACKUP_DIRECTORY}/{date_text}"
    try:
        existing = _read_storage_bytes(app_module, backup_prefix, backup_path)
    except (FileNotFoundError, OSError):
        existing = None
    if existing is not None:
        existing_sha256 = hashlib.sha256(existing).hexdigest()
        if existing_sha256 != old_sha256:
            raise RepairError("The title-repair backup path already contains different bytes.")
    else:
        _storage_write_bytes(
            app_module,
            backup_prefix,
            backup_path,
            original_bytes,
            original_filename=original_filename,
            purpose="backup",
        )
    verified = _read_storage_bytes(app_module, backup_prefix, backup_path)
    verified_sha256 = hashlib.sha256(verified).hexdigest()
    if verified_sha256 != old_sha256:
        raise RepairError("The title-repair backup checksum does not match the original bytes.")
    return {
        "path": backup_path,
        "prefix": backup_prefix,
        "name": backup_name,
        "sha256": verified_sha256,
        "size": len(verified),
    }


def _replace_certificate_storage(
    app_module: Any,
    target_path: str,
    replacement_bytes: bytes,
    original_filename: str,
) -> dict[str, Any]:
    prefix = _text(getattr(app_module, "STORAGE_PREFIX_REPORTS", REPORTS_PREFIX)) or REPORTS_PREFIX
    result = _storage_write_bytes(
        app_module,
        prefix,
        target_path,
        replacement_bytes,
        original_filename=original_filename,
        purpose="replacement",
    )
    written = _read_storage_bytes(app_module, prefix, target_path)
    if hashlib.sha256(written).hexdigest() != hashlib.sha256(bytes(replacement_bytes)).hexdigest():
        raise RepairError("The replacement certificate checksum does not match the generated bytes.")
    return result


def _restore_original(app_module: Any, target_path: str, original_bytes: bytes, original_filename: str) -> None:
    prefix = _text(getattr(app_module, "STORAGE_PREFIX_REPORTS", REPORTS_PREFIX)) or REPORTS_PREFIX
    _storage_write_bytes(
        app_module,
        prefix,
        target_path,
        original_bytes,
        original_filename=original_filename,
        purpose="restore",
    )
    restored = _read_storage_bytes(app_module, prefix, target_path)
    if hashlib.sha256(restored).hexdigest() != hashlib.sha256(bytes(original_bytes)).hexdigest():
        raise RepairError("The original certificate could not be restored after failure.")


def _db_session(app_module: Any) -> Any:
    return getattr(getattr(app_module, "db", None), "session", None)


def _validate_apply_guard(
    *,
    apply: bool,
    approval_ids: Sequence[int] | None,
    expected_count: int | None,
) -> None:
    if not apply:
        return
    if not approval_ids:
        raise RepairGuardError("--apply requires one or more explicit --approval-id values.")
    if expected_count is None:
        raise RepairGuardError("--apply requires --expected-count.")
    if expected_count != len(approval_ids):
        raise RepairGuardError(
            f"--expected-count {expected_count} does not match {len(approval_ids)} explicit approval ids."
        )


def _fresh_approval(app_module: Any, approval: Any) -> Any:
    session = _db_session(app_module)
    model = getattr(app_module, "CalibrationCertificateApproval", None)
    getter = getattr(session, "get", None)
    if callable(getter) and model is not None and getattr(approval, "id", None) is not None:
        fresh = getter(model, approval.id)
        if fresh is not None:
            return fresh
    return approval


def _assert_fresh_state(
    app_module: Any,
    approval: Any,
    inspection: Mapping[str, Any],
) -> tuple[Any, Any, Any]:
    session = _db_session(app_module)
    expire_all = getattr(session, "expire_all", None)
    if callable(expire_all):
        expire_all()
    fresh = _fresh_approval(app_module, approval)
    user = _approval_user(app_module, fresh)
    expected = {
        "status": "Approved",
        "is_latest": True,
        "approver_user_id": inspection.get("approver_user_id"),
        "approver_username": inspection.get("approver_username"),
        "shift_id": inspection.get("shift_id"),
        "online_tsr_submission_id": inspection.get("submission_id"),
        "signed_shift_file_id": inspection.get("signed_shift_file_id"),
        "no_signature_shift_file_id": inspection.get("no_signature_shift_file_id"),
        "certificate_number": inspection.get("certificate_number"),
        "revision_no": inspection.get("revision_no"),
        "approver_title_snapshot": inspection.get("stored_title"),
        "approver_name_snapshot": inspection.get("approver_name_snapshot"),
        "approver_signature_snapshot_sha256": inspection.get("approver_signature_snapshot_sha256"),
        "current_title": inspection.get("current_title"),
        "signed_filename": inspection.get("signed_filename"),
    }
    actual = {
        "status": _text(getattr(fresh, "status", "")),
        "is_latest": bool(getattr(fresh, "is_latest", False)),
        "approver_user_id": getattr(fresh, "approver_user_id", None),
        "approver_username": _username(user),
        "shift_id": getattr(fresh, "shift_id", None),
        "online_tsr_submission_id": getattr(fresh, "online_tsr_submission_id", None),
        "signed_shift_file_id": getattr(fresh, "signed_shift_file_id", None),
        "no_signature_shift_file_id": getattr(fresh, "no_signature_shift_file_id", None),
        "certificate_number": _text(getattr(fresh, "certificate_number", "")),
        "revision_no": getattr(fresh, "revision_no", None),
        "approver_title_snapshot": _text(getattr(fresh, "approver_title_snapshot", "")),
        "approver_name_snapshot": _text(getattr(fresh, "approver_name_snapshot", "")),
        "approver_signature_snapshot_sha256": hashlib.sha256(
            _text(getattr(fresh, "approver_signature_snapshot", "")).encode("utf-8")
        ).hexdigest(),
        "current_title": _text(getattr(user, "approval_title", "")),
        "signed_filename": _file_name(app_module, _signed_file_for_approval(app_module, fresh)) if _signed_file_for_approval(app_module, fresh) else "",
    }
    for key, expected_value in expected.items():
        if key in {"shift_id", "online_tsr_submission_id", "signed_shift_file_id", "no_signature_shift_file_id", "approver_user_id", "revision_no"}:
            if expected_value is not None and actual[key] != expected_value:
                raise RepairStaleError(f"{key} changed while preparing the repair.")
        elif key == "current_title":
            if actual[key] != expected_value:
                raise RepairStaleError("The approver's current title changed while preparing the repair.")
        elif actual[key] != expected_value:
            raise RepairStaleError(f"{key} changed while preparing the repair.")
    file_record = _signed_file_for_approval(app_module, fresh)
    if not file_record:
        raise RepairStaleError("The signed certificate linkage disappeared while preparing the repair.")
    target_path = _local_path(app_module, file_record)
    current_bytes = _read_signed_certificate_bytes(app_module, fresh, file_record)
    current_sha256 = hashlib.sha256(bytes(current_bytes)).hexdigest()
    if current_sha256 != inspection.get("old_sha256"):
        raise RepairStaleError("The signed certificate source hash changed while preparing the repair.")
    return fresh, file_record, current_bytes


def _apply_one(
    app_module: Any,
    approval: Any,
    inspection: Mapping[str, Any],
) -> dict[str, Any]:
    prepared = _prepare_repair(app_module, approval, inspection)
    fresh, file_record, original_bytes = _assert_fresh_state(app_module, approval, inspection)
    target_path = _local_path(app_module, file_record)
    original_filename = _file_name(app_module, file_record) or os.path.basename(target_path)
    backup = _backup_original(
        app_module,
        getattr(fresh, "id", None),
        target_path,
        original_bytes,
        original_filename,
    )
    # The backup itself can take a network round trip. Revalidate everything
    # immediately before replacing the live object.
    fresh, file_record, original_bytes = _assert_fresh_state(app_module, fresh, inspection)
    try:
        _replace_certificate_storage(app_module, target_path, prepared["bytes"], original_filename)
    except Exception:
        try:
            _restore_original(app_module, target_path, original_bytes, original_filename)
        except Exception as restore_error:
            raise RepairError(f"Storage replacement failed and restoration also failed: {restore_error}")
        raise

    session = _db_session(app_module)
    now_fn = getattr(app_module, "get_manila_time", None)
    now = now_fn() if callable(now_fn) else datetime.now()
    prior_title = _text(getattr(fresh, "approver_title_snapshot", ""))
    current_title = _text(inspection.get("current_title"))
    audit_metadata = {
        "repair_kind": "calibration_certificate_approver_title",
        "approval_id": getattr(fresh, "id", None),
        "certificate_number": _text(getattr(fresh, "certificate_number", "")),
        "approver_username": inspection.get("approver_username", ""),
        "prior_title": prior_title,
        "old_title": prior_title,
        "new_title": current_title,
        "current_title": current_title,
        "rendered_title_before": inspection.get("rendered_title", ""),
        "old_sha256": inspection.get("old_sha256", ""),
        "new_sha256": prepared["new_sha256"],
        "backup_sha256": backup["sha256"],
        "signed_shift_file_id": getattr(fresh, "signed_shift_file_id", None),
        "no_signature_shift_file_id": getattr(fresh, "no_signature_shift_file_id", None),
        "revision_no": getattr(fresh, "revision_no", None),
    }
    try:
        setattr(fresh, "approver_title_snapshot", current_title)
        setattr(fresh, "certificate_fingerprint", prepared["new_sha256"])
        setattr(fresh, "artifact_created_at", now)
        setattr(fresh, "updated_at", now)
        record_audit = getattr(app_module, "record_universal_approval_audit", None)
        if not callable(record_audit):
            raise RepairError("Universal approval audit helper is unavailable.")
        record_audit(
            "calibration_certificate",
            getattr(fresh, "id", None),
            AUDIT_ACTION,
            actor_user=SYSTEM_ACTOR,
            status_from="Approved",
            status_to="Approved",
            metadata=audit_metadata,
        )
        commit = getattr(session, "commit", None)
        if not callable(commit):
            raise RepairError("Database session commit is unavailable.")
        commit()
    except Exception as database_error:
        rollback = getattr(session, "rollback", None)
        if callable(rollback):
            rollback()
        try:
            _restore_original(app_module, target_path, original_bytes, original_filename)
        except Exception as restore_error:
            raise RepairError(
                f"Database update failed and original certificate restoration also failed: {restore_error}"
            ) from database_error
        raise RepairError(f"Database update failed; original certificate restored: {database_error}") from database_error
    return {
        **dict(inspection),
        "eligible": True,
        "applied": True,
        "backup_name": backup["name"],
        "backup_sha256": backup["sha256"],
        "new_sha256": prepared["new_sha256"],
        "rendered_title_after": prepared["verification"]["rendered_title"],
        "verification": prepared["verification"],
    }


def run_repair(
    app_module: Any,
    *,
    approvers: Sequence[str] | None = None,
    approval_ids: Sequence[int] | None = None,
    apply: bool = False,
    expected_count: int | None = None,
) -> dict[str, Any]:
    """Run one guarded dry-run/apply pass and return a JSON-safe report."""
    approvers = [
        _text(value).casefold() for value in (approvers or DEFAULT_APPROVERS)
    ]
    invalid_approvers = [value for value in approvers if value not in ALLOWED_APPROVERS]
    if invalid_approvers:
        raise RepairGuardError("Approver selection is limited to robert and rodito.")
    approvers = list(dict.fromkeys(approvers))
    _validate_apply_guard(
        apply=apply,
        approval_ids=approval_ids,
        expected_count=expected_count,
    )
    rows = _collect_approval_rows(
        app_module,
        approvers,
        approval_ids,
        ensure_schema=apply,
    )
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "approvers": approvers,
        "approval_ids": list(approval_ids or []),
        "expected_count": expected_count,
        "records": [],
        "errors": [],
        "summary": {
            "selected": len(rows),
            "eligible": 0,
            "already_current": 0,
            "applied": 0,
            "skipped": 0,
            "errors": 0,
        },
    }
    for approval in rows:
        approval_id = getattr(approval, "id", None) if approval is not None else None
        if approval is None:
            error = {"approval_id": approval_id, "error": "Approval record not found."}
            report["errors"].append(error)
            report["summary"]["errors"] += 1
            continue
        try:
            selected_username = _username(_approval_user(app_module, approval))
            if selected_username not in set(approvers):
                row = {
                    "approval_id": approval_id,
                    "certificate_number": _text(getattr(approval, "certificate_number", "")),
                    "approver_username": selected_username,
                    "eligible": False,
                    "reason": "approver-filtered",
                    "validations": [_validation("approver_filter", False, selected_username)],
                    "applied": False,
                    "skipped": True,
                }
                report["summary"]["skipped"] += 1
                if apply and approval_ids:
                    raise RepairError("The selected approval is assigned to an approver outside --approver.")
                report["records"].append(row)
                continue
            row = inspect_approval(app_module, approval)
            if row.get("reason") == "already-current":
                row["applied"] = False
                row["skipped"] = True
                report["summary"]["already_current"] += 1
                report["summary"]["skipped"] += 1
                report["records"].append(row)
                continue
            if not row.get("eligible"):
                row["applied"] = False
                row["skipped"] = True
                report["summary"]["skipped"] += 1
                if apply and approval_ids:
                    raise RepairError(row.get("reason") or "The selected approval is not repairable.")
                report["records"].append(row)
                continue
            report["summary"]["eligible"] += 1
            prepared = _prepare_repair(app_module, approval, row)
            row = {
                **row,
                "new_sha256": prepared["new_sha256"],
                "rendered_title_after": prepared["verification"]["rendered_title"],
                "verification": prepared["verification"],
                "applied": False,
            }
            if apply:
                row = _apply_one(app_module, approval, row)
                report["summary"]["applied"] += 1
            else:
                row["skipped"] = False
            report["records"].append(row)
        except Exception as repair_error:
            report["errors"].append({
                "approval_id": approval_id,
                "certificate_number": _text(getattr(approval, "certificate_number", "")),
                "error": str(repair_error),
            })
            report["summary"]["errors"] += 1
    return report


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _validate_apply_guard(
            apply=args.apply,
            approval_ids=args.approval_ids,
            expected_count=args.expected_count,
        )
        # Import only after argument parsing so ``--help`` and guard failures do
        # not initialize the Flask app or touch the configured database.
        try:
            import app as app_module
        except ModuleNotFoundError as import_error:
            if import_error.name != "app":
                raise
            repository_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if repository_root not in sys.path:
                sys.path.insert(0, repository_root)
            import app as app_module

        with app_module.app.app_context():
            report = run_repair(
                app_module,
                approvers=args.approvers,
                approval_ids=args.approval_ids,
                apply=args.apply,
                expected_count=args.expected_count,
            )
    except RepairGuardError as guard_error:
        print(json.dumps({"status": "error", "error": str(guard_error)}, ensure_ascii=False, indent=2))
        return 2
    except Exception as command_error:
        print(json.dumps({"status": "error", "error": str(command_error)}, ensure_ascii=False, indent=2))
        return 1
    report["status"] = "success" if not report["errors"] else "partial_success"
    report["message"] = (
        "Dry run complete. No database or managed-storage objects were changed."
        if not args.apply
        else "Calibration Certificate title repair complete; see records and errors for per-approval results."
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

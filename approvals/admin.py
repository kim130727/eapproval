from __future__ import annotations

import csv
import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

from django.contrib import admin, messages
from django.http import FileResponse, HttpRequest, HttpResponse
from django.template.defaultfilters import truncatechars
from django.utils import timezone
from django.utils.html import format_html

from .models import Attachment, Document, DocumentLine


# -----------------------------
# Shared helpers
# -----------------------------
_ILLEGAL_FS_CHARS = r'\\/:*?"<>|'
_ILLEGAL_FS_RE = re.compile(f"[{re.escape(_ILLEGAL_FS_CHARS)}]")


def safe_component(value: object, default: str = "untitled") -> str:
    """
    Make a string safe to be used in filenames / zip arcnames.
    """
    s = str(value or "").strip()
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = _ILLEGAL_FS_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else default


def unique_arcname(used: set[str], arcname: str) -> str:
    """
    Ensure arcname is unique within a zip by appending " (2)", " (3)", ...
    """
    if arcname not in used:
        used.add(arcname)
        return arcname

    p = Path(arcname)
    stem, suffix = p.stem, p.suffix
    parent = str(p.parent)
    if parent == ".":
        parent = ""

    i = 2
    while True:
        candidate_name = f"{stem} ({i}){suffix}"
        candidate = f"{parent}/{candidate_name}" if parent else candidate_name
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def display_name(user) -> str:
    """
    profile.display_name() -> profile.full_name -> user.get_full_name() -> user.username -> "-"
    """
    if not user:
        return "-"

    profile = getattr(user, "profile", None)
    if profile:
        method = getattr(profile, "display_name", None)
        if callable(method):
            try:
                value = method()
                if value:
                    return str(value)
            except Exception:
                pass

        value = getattr(profile, "full_name", None)
        if value:
            return str(value)

    try:
        value = user.get_full_name()
        if value:
            return str(value)
    except Exception:
        pass

    value = getattr(user, "username", None)
    return str(value) if value else "-"


def local_dt(dt) -> str:
    if not dt:
        return ""
    try:
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


def _zip_response_from_spooled_file(
    spooled_file, download_name: str, content_type: str = "application/zip"
) -> FileResponse:
    spooled_file.seek(0)
    resp = FileResponse(spooled_file, as_attachment=True, filename=download_name)
    resp["Content-Type"] = content_type
    return resp


# -----------------------------
# Document Admin
# -----------------------------
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    actions = ["export_documents_csv", "download_documents_attachments_zip"]

    list_display = (
        "id",
        "title",
        "content_preview",
        "status",
        "created_by_display",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("title", "content")
    ordering = ("-id",)

    @admin.display(description="작성자")
    def created_by_display(self, obj: Document) -> str:
        return display_name(getattr(obj, "created_by", None))

    @admin.display(description="Content")
    def content_preview(self, obj: Document) -> str:
        return truncatechars(getattr(obj, "content", "") or "", 80)

    @admin.action(description="선택 문서 CSV 다운로드")
    def export_documents_csv(self, request: HttpRequest, queryset):
        if not queryset.exists():
            self.message_user(request, "선택된 문서가 없습니다.", level=messages.WARNING)
            return None

        qs = queryset.select_related("created_by")

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "title", "content", "status", "created_by", "created_at", "updated_at"])

        for doc in qs:
            writer.writerow(
                [
                    doc.id,
                    getattr(doc, "title", ""),
                    getattr(doc, "content", ""),
                    getattr(doc, "status", ""),
                    display_name(getattr(doc, "created_by", None)),
                    local_dt(getattr(doc, "created_at", None)),
                    local_dt(getattr(doc, "updated_at", None)),
                ]
            )

        csv_bytes = buffer.getvalue().encode("utf-8-sig")
        filename = f"documents_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @admin.action(description="선택 문서의 첨부파일 ZIP 다운로드")
    def download_documents_attachments_zip(self, request: HttpRequest, queryset):
        if not queryset.exists():
            self.message_user(request, "선택된 문서가 없습니다.", level=messages.WARNING)
            return None

        qs = queryset.prefetch_related("attachments")

        spooled = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024, mode="w+b")
        used_names: set[str] = set()
        wrote_any = False

        with zipfile.ZipFile(spooled, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for doc in qs:
                folder = safe_component(f"doc_{doc.id}_{getattr(doc, 'title', '')}")
                atts = list(getattr(doc, "attachments", []).all())

                for att in atts:
                    f = getattr(att, "file", None)
                    if not f:
                        continue

                    try:
                        original_name = os.path.basename(getattr(f, "name", "") or "")
                        safe_name = safe_component(original_name or f"attachment_{att.id}")
                        arcname = unique_arcname(used_names, f"{folder}/{safe_name}")

                        f.open("rb")
                        try:
                            data = f.read()
                        finally:
                            try:
                                f.close()
                            except Exception:
                                pass

                        zf.writestr(arcname, data)
                        wrote_any = True
                    except Exception:
                        continue

        if not wrote_any:
            self.message_user(
                request,
                "선택된 문서들에 다운로드할 첨부파일이 없습니다.",
                level=messages.WARNING,
            )
            try:
                spooled.close()
            except Exception:
                pass
            return None

        filename = f"documents_attachments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return _zip_response_from_spooled_file(spooled, filename)


# -----------------------------
# DocumentLine Admin
# -----------------------------
@admin.register(DocumentLine)
class DocumentLineAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "order", "role", "user_display", "decision", "acted_at")
    list_filter = ("role", "decision", "acted_at")
    search_fields = ("document__title", "user__username", "user__first_name", "user__last_name")
    ordering = ("document_id", "order", "id")

    @admin.display(description="대상")
    def user_display(self, obj: DocumentLine) -> str:
        return display_name(getattr(obj, "user", None))


# -----------------------------
# Attachment Admin
# -----------------------------
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    actions = ["export_attachments_csv", "download_attachments_zip"]

    list_display = ("id", "document", "file_link", "uploader_display", "created_at")
    list_filter = ("created_at",)
    search_fields = ("document__title", "file")
    ordering = ("-id",)

    @admin.display(description="업로더")
    def uploader_display(self, obj: Attachment) -> str:
        user = getattr(obj, "uploaded_by", None) or getattr(obj, "uploader", None)
        return display_name(user)

    @admin.display(description="파일")
    def file_link(self, obj: Attachment) -> str:
        f = getattr(obj, "file", None)
        if not f:
            return "-"
        url = getattr(f, "url", "")
        name = os.path.basename(getattr(f, "name", "") or "") or "download"
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, name)

    @admin.action(description="선택 첨부파일 CSV 다운로드")
    def export_attachments_csv(self, request: HttpRequest, queryset):
        if not queryset.exists():
            self.message_user(request, "선택된 첨부파일이 없습니다.", level=messages.WARNING)
            return None

        qs = queryset.select_related("document", "uploaded_by")

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "document_id",
                "document_title",
                "file_name",
                "file_path",
                "uploader",
                "created_at",
            ]
        )

        for att in qs:
            doc = getattr(att, "document", None)
            f = getattr(att, "file", None)
            file_path = getattr(f, "name", "") if f else ""
            file_name = os.path.basename(file_path) if file_path else ""
            user = getattr(att, "uploaded_by", None) or getattr(att, "uploader", None)

            writer.writerow(
                [
                    att.id,
                    getattr(doc, "id", ""),
                    getattr(doc, "title", "") if doc else "",
                    file_name,
                    file_path,
                    display_name(user),
                    local_dt(getattr(att, "created_at", None)),
                ]
            )

        csv_bytes = buffer.getvalue().encode("utf-8-sig")
        filename = f"attachments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        resp = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @admin.action(description="선택 첨부파일 ZIP 다운로드")
    def download_attachments_zip(self, request: HttpRequest, queryset):
        if not queryset.exists():
            self.message_user(request, "선택된 첨부파일이 없습니다.", level=messages.WARNING)
            return None

        qs = queryset.select_related("document")

        spooled = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024, mode="w+b")
        used_names: set[str] = set()
        wrote_any = False

        with zipfile.ZipFile(spooled, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for att in qs:
                f = getattr(att, "file", None)
                if not f:
                    continue

                doc = getattr(att, "document", None)
                folder = safe_component(
                    f"doc_{getattr(doc, 'id', 'x')}_{getattr(doc, 'title', '')}" if doc else "no_document"
                )

                try:
                    original_name = os.path.basename(getattr(f, "name", "") or "")
                    safe_name = safe_component(original_name or f"attachment_{att.id}")
                    arcname = unique_arcname(used_names, f"{folder}/{safe_name}")

                    f.open("rb")
                    try:
                        data = f.read()
                    finally:
                        try:
                            f.close()
                        except Exception:
                            pass

                    zf.writestr(arcname, data)
                    wrote_any = True
                except Exception:
                    continue

        if not wrote_any:
            self.message_user(
                request,
                "다운로드할 첨부파일이 없습니다.",
                level=messages.WARNING,
            )
            try:
                spooled.close()
            except Exception:
                pass
            return None

        filename = f"attachments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return _zip_response_from_spooled_file(spooled, filename)

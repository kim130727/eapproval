# approvals/admin.py
import csv
import io
import os
import zipfile

from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Attachment, Document, DocumentLine


# --------------------------------------------
# 표시 이름 (Profile 우선)
# --------------------------------------------
def display_name(user) -> str:
    if not user:
        return "-"

    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None

    if profile:
        # 1) profile.display_name() 우선
        try:
            if hasattr(profile, "display_name"):
                name = profile.display_name()
                if name:
                    return str(name).strip()
        except Exception:
            pass

        # 2) profile.full_name fallback
        name = (getattr(profile, "full_name", "") or "").strip()
        if name:
            return name

    # 3) user.get_full_name() fallback
    if hasattr(user, "get_full_name"):
        name = (user.get_full_name() or "").strip()
        if name:
            return name

    # 4) username fallback
    return (getattr(user, "username", "") or "-").strip() or "-"


# --------------------------------------------
# 시간 문자열
# --------------------------------------------
def now_stamp() -> str:
    return timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")


# --------------------------------------------
# 안전한 파일명/폴더명
# --------------------------------------------
def safe_component(s: str) -> str:
    s = (s or "").strip()
    s = "".join(ch for ch in s if ch not in r'\/:*?"<>|')
    s = s.replace("\n", " ").replace("\r", " ").strip()
    return s or "untitled"


# --------------------------------------------
# ZIP 내 중복 경로 방지
# --------------------------------------------
def unique_arcname(used: set, arcname: str) -> str:
    if arcname not in used:
        used.add(arcname)
        return arcname

    base, ext = os.path.splitext(arcname)
    i = 2
    while True:
        cand = f"{base} ({i}){ext}"
        if cand not in used:
            used.add(cand)
            return cand
        i += 1


# --------------------------------------------
# Document Admin
# --------------------------------------------
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "created_by_name",
        "status",
        "current_line_order",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "title",
        "content",
        "created_by__username",
        "created_by__profile__full_name",
    )
    ordering = ("-id",)

    actions = [
        "export_selected_csv",
        "download_attachments_zip",
    ]

    @admin.display(description="작성자")
    def created_by_name(self, obj):
        return display_name(getattr(obj, "created_by", None))

    # ----------------------------------------
    # CSV 다운로드
    # ----------------------------------------
    @admin.action(description="선택 문서 CSV 저장")
    def export_selected_csv(self, request, queryset):
        qs = queryset.select_related("created_by")

        if not qs.exists():
            self.message_user(request, "선택된 문서가 없습니다.", level=messages.WARNING)
            return None

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(
            ["id", "status", "title", "created_by", "current_line_order", "created_at", "updated_at"]
        )

        for doc in qs:
            created_at = getattr(doc, "created_at", None)
            updated_at = getattr(doc, "updated_at", None)

            writer.writerow(
                [
                    doc.id,
                    doc.get_status_display(),
                    doc.title,
                    display_name(getattr(doc, "created_by", None)),
                    getattr(doc, "current_line_order", ""),
                    timezone.localtime(created_at).strftime("%Y-%m-%d %H:%M") if created_at else "",
                    timezone.localtime(updated_at).strftime("%Y-%m-%d %H:%M") if updated_at else "",
                ]
            )

        content = buffer.getvalue().encode("utf-8-sig")  # ✅ 엑셀 BOM
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="documents_{now_stamp()}.csv"'
        return response

    # ----------------------------------------
    # 첨부파일 ZIP 다운로드 (선택 문서들)
    # ----------------------------------------
    @admin.action(description="선택 문서 첨부파일 ZIP 다운로드")
    def download_attachments_zip(self, request, queryset):
        qs = queryset.prefetch_related("attachments")

        if not qs.exists():
            self.message_user(request, "선택된 문서가 없습니다.", level=messages.WARNING)
            return None

        memory = io.BytesIO()
        used: set[str] = set()
        wrote_any = False

        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for doc in qs:
                doc_folder = f"doc_{doc.id}_{safe_component(getattr(doc, 'title', ''))}"

                for att in doc.attachments.all():
                    file_field = getattr(att, "file", None)
                    if not file_field:
                        continue

                    try:
                        src_name = file_field.name or ""
                        base = os.path.basename(src_name) if src_name else "file"
                        filename = safe_component(base)

                        arcname = unique_arcname(used, f"{doc_folder}/{filename}")

                        with file_field.open("rb") as f:
                            zf.writestr(arcname, f.read())
                            wrote_any = True
                    except Exception:
                        # 파일 하나가 깨져도 전체 zip은 최대한 만들어지게
                        continue

        if not wrote_any:
            self.message_user(request, "선택 문서들에 첨부파일이 없습니다.", level=messages.WARNING)
            return None

        memory.seek(0)
        filename = f"attachments_{now_stamp()}.zip"
        return FileResponse(
            memory,
            as_attachment=True,
            filename=filename,
            content_type="application/zip",
        )


# --------------------------------------------
# DocumentLine Admin
# --------------------------------------------
@admin.register(DocumentLine)
class DocumentLineAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "role",
        "order",
        "user_name",
        "decision",
        "acted_at",
    )
    list_filter = ("role", "decision")
    search_fields = (
        "document__title",
        "user__username",
        "user__profile__full_name",
    )
    ordering = ("-id",)

    @admin.display(description="대상")
    def user_name(self, obj):
        return display_name(getattr(obj, "user", None))


# --------------------------------------------
# Attachment Admin
# --------------------------------------------
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "file_link",
        "uploaded_by_name",
        "created_at",
    )
    search_fields = (
        "document__title",
        "uploaded_by__username",
        "uploaded_by__profile__full_name",
        "file",
    )
    ordering = ("-id",)

    actions = [
        "download_selected_zip",
    ]

    @admin.display(description="파일")
    def file_link(self, obj):
        try:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, obj.file.name)
        except Exception:
            return getattr(getattr(obj, "file", None), "name", "-") or "-"

    @admin.display(description="업로더")
    def uploaded_by_name(self, obj):
        return display_name(getattr(obj, "uploaded_by", None))

    # ----------------------------------------
    # 선택 첨부파일 ZIP 다운로드
    # ----------------------------------------
    @admin.action(description="선택 첨부파일 ZIP 다운로드")
    def download_selected_zip(self, request, queryset):
        qs = queryset.select_related("document")

        if not qs.exists():
            self.message_user(request, "선택된 첨부파일이 없습니다.", level=messages.WARNING)
            return None

        memory = io.BytesIO()
        used: set[str] = set()
        wrote_any = False

        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for att in qs:
                doc = getattr(att, "document", None)
                doc_folder = f"doc_{getattr(doc, 'id', 'x')}_{safe_component(getattr(doc, 'title', ''))}"

                file_field = getattr(att, "file", None)
                if not file_field:
                    continue

                try:
                    src_name = file_field.name or ""
                    base = os.path.basename(src_name) if src_name else "file"
                    filename = safe_component(base)

                    arcname = unique_arcname(used, f"{doc_folder}/{filename}")

                    with file_field.open("rb") as f:
                        zf.writestr(arcname, f.read())
                        wrote_any = True
                except Exception:
                    continue

        if not wrote_any:
            self.message_user(request, "선택한 첨부파일에 실제 파일이 없습니다.", level=messages.WARNING)
            return None

        memory.seek(0)
        filename = f"attachments_selected_{now_stamp()}.zip"
        return FileResponse(
            memory,
            as_attachment=True,
            filename=filename,
            content_type="application/zip",
        )
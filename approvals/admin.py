# approvals/admin.py

import csv
import io
import os
import zipfile

from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Document, DocumentLine, Attachment


# --------------------------------------------
# 표시 이름 (Profile 우선)
# --------------------------------------------
def display_name(user):
    if not user:
        return "-"

    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None

    if profile:
        try:
            if hasattr(profile, "display_name"):
                name = profile.display_name()
                if name:
                    return name
        except Exception:
            pass

        name = (getattr(profile, "full_name", "") or "").strip()
        if name:
            return name

    if hasattr(user, "get_full_name"):
        name = (user.get_full_name() or "").strip()
        if name:
            return name

    return user.username


# --------------------------------------------
# 시간 문자열
# --------------------------------------------
def now_stamp():
    return timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")


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

    # ----------------------------------------
    # 작성자 표시
    # ----------------------------------------
    def created_by_name(self, obj):
        return display_name(obj.created_by)

    created_by_name.short_description = "작성자"

    # ----------------------------------------
    # CSV 다운로드
    # ----------------------------------------
    def export_selected_csv(self, request, queryset):

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(
            [
                "id",
                "status",
                "title",
                "created_by",
                "current_line_order",
                "created_at",
                "updated_at",
            ]
        )

        for doc in queryset:

            writer.writerow(
                [
                    doc.id,
                    doc.get_status_display(),
                    doc.title,
                    display_name(doc.created_by),
                    doc.current_line_order,
                    doc.created_at.strftime("%Y-%m-%d %H:%M"),
                    doc.updated_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )

        content = buffer.getvalue().encode("utf-8-sig")

        response = HttpResponse(
            content,
            content_type="text/csv; charset=utf-8",
        )

        response["Content-Disposition"] = (
            f'attachment; filename="documents_{now_stamp()}.csv"'
        )

        return response

    export_selected_csv.short_description = "선택 문서 CSV 저장"

    # ----------------------------------------
    # 첨부파일 ZIP 다운로드
    # ----------------------------------------
    def download_attachments_zip(self, request, queryset):

        memory = io.BytesIO()

        with zipfile.ZipFile(
            memory,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as zf:

            for doc in queryset:

                attachments = doc.attachments.all()

                for att in attachments:

                    filename = os.path.basename(att.file.name)

                    folder = f"doc_{doc.id}"

                    arcname = f"{folder}/{filename}"

                    with att.file.open("rb") as f:
                        zf.writestr(arcname, f.read())

        memory.seek(0)

        filename = f"attachments_{now_stamp()}.zip"

        return FileResponse(
            memory,
            as_attachment=True,
            filename=filename,
        )

    download_attachments_zip.short_description = "선택 문서 첨부파일 ZIP 다운로드"


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

    list_filter = (
        "role",
        "decision",
    )

    search_fields = (
        "document__title",
        "user__username",
        "user__profile__full_name",
    )

    ordering = ("-id",)

    def user_name(self, obj):
        return display_name(obj.user)

    user_name.short_description = "대상"


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

    # ----------------------------------------
    # 파일 링크
    # ----------------------------------------
    def file_link(self, obj):

        try:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.file.url,
                obj.file.name,
            )
        except Exception:
            return obj.file.name

    file_link.short_description = "파일"

    # ----------------------------------------
    # 업로더 표시
    # ----------------------------------------
    def uploaded_by_name(self, obj):
        return display_name(obj.uploaded_by)

    uploaded_by_name.short_description = "업로더"

    # ----------------------------------------
    # 선택 첨부파일 ZIP 다운로드
    # ----------------------------------------
    def download_selected_zip(self, request, queryset):

        memory = io.BytesIO()

        with zipfile.ZipFile(
            memory,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as zf:

            for att in queryset:

                doc = att.document
                filename = os.path.basename(att.file.name)

                folder = f"doc_{doc.id}"

                arcname = f"{folder}/{filename}"

                with att.file.open("rb") as f:
                    zf.writestr(arcname, f.read())

        memory.seek(0)

        filename = f"attachments_selected_{now_stamp()}.zip"

        return FileResponse(
            memory,
            as_attachment=True,
            filename=filename,
        )

    download_selected_zip.short_description = "선택 첨부파일 ZIP 다운로드"
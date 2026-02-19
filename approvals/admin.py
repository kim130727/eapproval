from django.contrib import admin
from .models import Document, DocumentLine, Attachment
from accounts.models import Profile


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "status", "current_line_order", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "content", "created_by__username")


@admin.register(DocumentLine)
class DocumentLineAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "role", "order", "user", "decision", "acted_at")
    list_filter = ("role", "decision")
    search_fields = ("document__title", "user__username")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "file", "uploaded_by", "created_at")
    search_fields = ("document__title", "uploaded_by__username")

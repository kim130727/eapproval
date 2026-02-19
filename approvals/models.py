from django.conf import settings
from django.db import models
from django.utils import timezone


class Document(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "임시"
        SUBMITTED = "SUBMITTED", "상신"
        IN_PROGRESS = "IN_PROGRESS", "진행중"
        REJECTED = "REJECTED", "반려"
        COMPLETED = "COMPLETED", "완료"

    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="docs_created"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    current_line_order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"[{self.get_status_display()}] {self.title}"


class DocumentLine(models.Model):
    class Role(models.TextChoices):
        CONSULT = "CONSULT", "협의"
        APPROVE = "APPROVE", "결재"
        RECEIVE = "RECEIVE", "수신/열람"

    class Decision(models.TextChoices):
        PENDING = "PENDING", "대기"
        APPROVED = "APPROVED", "승인"
        REJECTED = "REJECTED", "반려"
        READ = "READ", "열람"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="lines")
    role = models.CharField(max_length=10, choices=Role.choices)
    order = models.PositiveIntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    comment = models.CharField(max_length=300, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.document_id} {self.role}#{self.order} {self.user}"


def attachment_upload_to(instance, filename: str) -> str:
    dt = timezone.localtime(timezone.now())
    return f"attachments/{dt:%Y/%m}/{filename}"


class Attachment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_upload_to)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.file.name

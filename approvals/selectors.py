from django.db.models import F, Q
from .models import Document, DocumentLine


def my_documents(user):
    return Document.objects.filter(created_by=user).order_by("-id")


def inbox_pending(user):
    return (
        Document.objects.filter(
            status=Document.Status.IN_PROGRESS,
            lines__user=user,
            lines__decision=DocumentLine.Decision.PENDING,
            lines__order=F("current_line_order"),
            lines__role__in=[DocumentLine.Role.CONSULT, DocumentLine.Role.APPROVE],
        )
        .distinct()
        .order_by("-id")
    )


def received_docs(user):
    return (
        Document.objects.filter(
            status=Document.Status.COMPLETED,
            lines__user=user,
            lines__role=DocumentLine.Role.RECEIVE,
        )
        .distinct()
        .order_by("-id")
    )


# ✅ 추가: 완료함 (내가 상신했거나 / 결재라인에 포함된 완료 문서)
def completed_docs(user):
    return (
        Document.objects.filter(status=Document.Status.COMPLETED)
        .filter(Q(created_by=user) | Q(lines__user=user))
        .distinct()
        .order_by("-id")
    )


# ✅ 추가: 반려함 (내가 상신했거나 / 결재라인에 포함된 반려 문서)
def rejected_docs(user):
    return (
        Document.objects.filter(status=Document.Status.REJECTED)
        .filter(Q(created_by=user) | Q(lines__user=user))
        .distinct()
        .order_by("-id")
    )
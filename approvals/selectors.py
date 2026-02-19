from django.db.models import F
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

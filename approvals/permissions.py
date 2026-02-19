#approvals/permissions.py
from .models import Document, DocumentLine

CHAIR_GROUP = "CHAIR"


def is_chair(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=CHAIR_GROUP).exists()


def can_view_document(user, doc: Document) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if doc.created_by_id == user.id:
        return True
    if doc.lines.filter(user_id=user.id).exists():
        return True
    if doc.attachments.filter(uploaded_by_id=user.id).exists():
        return True
    return False


def can_act_on_line(user, line: DocumentLine) -> bool:
    return user.is_authenticated and (user.is_superuser or line.user_id == user.id)

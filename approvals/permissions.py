from django.contrib.auth.models import Group
from .models import Document, DocumentLine


CHAIR_GROUP = "CHAIR"  # ✅ 위원장 그룹명


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
    # 본인 라인만 처리 가능 (위원장은 대리처리 허용하려면 여기에서 풀어도 됨)
    return user.is_authenticated and (user.is_superuser or line.user_id == user.id)

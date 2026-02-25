# approvals/services.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import Attachment, Document, DocumentLine
from .notify import (
    notify_on_completed,
    notify_on_line_approved,
    notify_on_rejected,
    notify_on_submit,
)


def _active_roles():
    return [DocumentLine.Role.CONSULT, DocumentLine.Role.APPROVE]


def _next_pending_line(doc: Document):
    # 현재 order에서 처리할 pending 1건
    return doc.lines.filter(
        role__in=_active_roles(),
        order=doc.current_line_order,
        decision=DocumentLine.Decision.PENDING,
    ).first()


@transaction.atomic
def create_document_with_lines_and_files(
    *,
    creator,
    title: str,
    content: str,
    consultants,
    approvers,
    receivers,
    files,
    request=None,
) -> Document:
    doc = Document.objects.create(
        title=title,
        content=content,
        created_by=creator,
        status=Document.Status.SUBMITTED,
        current_line_order=1,
    )

    order = 1
    for u in consultants:
        DocumentLine.objects.create(
            document=doc, role=DocumentLine.Role.CONSULT, order=order, user=u
        )
        order += 1

    for u in approvers:
        DocumentLine.objects.create(
            document=doc, role=DocumentLine.Role.APPROVE, order=order, user=u
        )
        order += 1

    for u in receivers:
        DocumentLine.objects.create(
            document=doc, role=DocumentLine.Role.RECEIVE, order=order, user=u
        )
        order += 1

    for f in files:
        Attachment.objects.create(document=doc, file=f, uploaded_by=creator)

    if doc.lines.filter(role__in=_active_roles()).exists():
        doc.status = Document.Status.IN_PROGRESS
    else:
        doc.status = Document.Status.COMPLETED

    doc.save(update_fields=["status"])

    # ✅ 상신 알림(협의자+결재자): notify.py 시그니처에 맞춤
    notify_on_submit(request=request, doc=doc, user=creator)

    # ✅ 결재자가 없어서 즉시 완료라면 완료 알림
    if doc.status == Document.Status.COMPLETED:
        notify_on_completed(request=request, doc=doc, user=creator)

    return doc


@transaction.atomic
def approve_or_consult(
    *,
    doc: Document,
    actor,
    comment: str = "",
    request=None,
) -> Document:
    line = _next_pending_line(doc)
    if not line:
        return doc

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.APPROVED
    line.comment = (comment or "")[:300]
    line.acted_at = timezone.now()
    line.save(update_fields=["decision", "comment", "acted_at"])

    doc.current_line_order += 1

    # 다음 라인이 없으면 완료
    if _next_pending_line(doc) is None:
        doc.status = Document.Status.COMPLETED
    else:
        doc.status = Document.Status.IN_PROGRESS

    doc.save(update_fields=["current_line_order", "status"])

    # ✅ 다음 처리자 알림(또는 완료 알림): notify.py 시그니처에 맞춤
    notify_on_line_approved(request=request, doc=doc, user=actor)

    return doc


@transaction.atomic
def reject(
    *,
    doc: Document,
    actor,
    comment: str,
    request=None,
) -> Document:
    line = _next_pending_line(doc)
    if not line:
        return doc

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.REJECTED
    line.comment = (comment or "")[:300]
    line.acted_at = timezone.now()
    line.save(update_fields=["decision", "comment", "acted_at"])

    doc.status = Document.Status.REJECTED
    doc.save(update_fields=["status"])

    # ✅ 반려 알림(상신자): notify.py 시그니처에 맞춤
    notify_on_rejected(
        request=request,
        doc=doc,
        user=getattr(doc, "created_by", None),
        reason=(comment or "")[:300],
    )

    return doc


@transaction.atomic
def mark_read(*, doc: Document, actor) -> Document:
    line = doc.lines.filter(
        role=DocumentLine.Role.RECEIVE,
        user_id=actor.id,
    ).first()
    if not line:
        return doc

    if line.decision == DocumentLine.Decision.PENDING:
        line.decision = DocumentLine.Decision.READ
        line.acted_at = timezone.now()
        line.save(update_fields=["decision", "acted_at"])

    return doc
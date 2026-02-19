from django.db import transaction
from django.utils import timezone

from .models import Attachment, Document, DocumentLine


def _active_roles():
    return [DocumentLine.Role.CONSULT, DocumentLine.Role.APPROVE]


def _next_pending_line(doc: Document):
    return doc.lines.filter(
        role__in=_active_roles(),
        order=doc.current_line_order,
        decision=DocumentLine.Decision.PENDING,
    ).first()


@transaction.atomic
def create_document_with_lines_and_files(
    *, creator, title: str, content: str, consultants, approvers, receivers, files
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
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.CONSULT, order=order, user=u)
        order += 1

    for u in approvers:
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.APPROVE, order=order, user=u)
        order += 1

    for u in receivers:
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.RECEIVE, order=order, user=u)
        order += 1

    for f in files:
        Attachment.objects.create(document=doc, file=f, uploaded_by=creator)

    if doc.lines.filter(role__in=_active_roles()).exists():
        doc.status = Document.Status.IN_PROGRESS
    else:
        doc.status = Document.Status.COMPLETED
    doc.save(update_fields=["status"])
    return doc


@transaction.atomic
def approve_or_consult(*, doc: Document, actor, comment: str = "") -> Document:
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
    if _next_pending_line(doc) is None:
        doc.status = Document.Status.COMPLETED
    else:
        doc.status = Document.Status.IN_PROGRESS
    doc.save(update_fields=["current_line_order", "status"])
    return doc


@transaction.atomic
def reject(*, doc: Document, actor, comment: str) -> Document:
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
    return doc


@transaction.atomic
def mark_read(*, doc: Document, actor) -> Document:
    line = doc.lines.filter(role=DocumentLine.Role.RECEIVE, user_id=actor.id).first()
    if not line:
        return doc

    if line.decision == DocumentLine.Decision.PENDING:
        line.decision = DocumentLine.Decision.READ
        line.acted_at = timezone.now()
        line.save(update_fields=["decision", "acted_at"])
    return doc

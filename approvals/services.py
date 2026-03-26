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


def _pending_consult_lines(doc: Document):
    """
    아직 처리되지 않은 협의 라인 전체
    협의자는 동시 승인 대상
    """
    return doc.lines.filter(
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")


def _pending_approve_lines(doc: Document):
    """
    아직 처리되지 않은 결재 라인 전체
    결재자는 순차 승인 대상
    """
    return doc.lines.filter(
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")


def _current_pending_approve_line(doc: Document):
    """
    현재 처리 가능한 결재자 1명
    = 아직 남아 있는 결재 라인 중 order가 가장 작은 1건
    """
    return _pending_approve_lines(doc).first()


def _has_active_lines(doc: Document) -> bool:
    return doc.lines.filter(role__in=_active_roles()).exists()


def _recalculate_doc_status_and_order(doc: Document) -> Document:
    """
    문서의 현재 진행 상태와 current_line_order를 재계산한다.

    정책:
    1) 협의 미처리자가 한 명이라도 있으면 협의 단계 진행중
    2) 협의가 모두 끝났고 결재 미처리자가 있으면 가장 빠른 결재 order 진행중
    3) 둘 다 없으면 완료
    """
    pending_consults = _pending_consult_lines(doc)
    if pending_consults.exists():
        first_consult = pending_consults.first()
        doc.current_line_order = first_consult.order
        doc.status = Document.Status.IN_PROGRESS
        doc.save(update_fields=["current_line_order", "status"])
        return doc

    current_approve = _current_pending_approve_line(doc)
    if current_approve:
        doc.current_line_order = current_approve.order
        doc.status = Document.Status.IN_PROGRESS
        doc.save(update_fields=["current_line_order", "status"])
        return doc

    doc.status = Document.Status.COMPLETED
    doc.save(update_fields=["status"])
    return doc


def _get_actionable_line_for_actor(doc: Document, actor):
    """
    현재 actor가 처리할 수 있는 라인을 반환한다.

    정책:
    - 협의가 하나라도 남아 있으면:
      -> 협의자는 자기 협의 라인을 동시 처리 가능
      -> 결재자는 처리 불가
    - 협의가 모두 끝났으면:
      -> 현재 순차 결재자 1명만 처리 가능
    """
    if actor.is_superuser:
        pending_consults = _pending_consult_lines(doc)
        if pending_consults.exists():
            return pending_consults.filter(user_id=actor.id).first() or pending_consults.first()

        return _current_pending_approve_line(doc)

    pending_consults = _pending_consult_lines(doc)
    if pending_consults.exists():
        return pending_consults.filter(user_id=actor.id).first()

    current_approve = _current_pending_approve_line(doc)
    if current_approve and current_approve.user_id == actor.id:
        return current_approve

    return None


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

    # 협의자: 동시 승인 대상이므로 모두 같은 단계로 보아도 되지만
    # 현재 구조에서는 기존 order 유지 가능.
    # 진행 판단은 "CONSULT 전체 pending 존재 여부"로 한다.
    for u in consultants:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.CONSULT,
            order=order,
            user=u,
        )
        order += 1

    # 결재자: 순차 승인
    for u in approvers:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=order,
            user=u,
        )
        order += 1

    # 수신자: 완료 후 열람
    for u in receivers:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.RECEIVE,
            order=order,
            user=u,
        )
        order += 1

    for f in files:
        Attachment.objects.create(document=doc, file=f, uploaded_by=creator)

    if _has_active_lines(doc):
        _recalculate_doc_status_and_order(doc)
    else:
        doc.status = Document.Status.COMPLETED
        doc.save(update_fields=["status"])

    notify_on_submit(request=request, doc=doc, user=creator)

    return doc


@transaction.atomic
def approve_or_consult(
    *,
    doc: Document,
    actor,
    comment: str = "",
    request=None,
) -> Document:
    line = _get_actionable_line_for_actor(doc, actor)
    if not line:
        raise PermissionError("처리 권한이 없습니다.")

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.APPROVED
    line.comment = (comment or "")[:300]
    line.acted_at = timezone.now()
    line.save(update_fields=["decision", "comment", "acted_at"])

    _recalculate_doc_status_and_order(doc)

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
    line = _get_actionable_line_for_actor(doc, actor)
    if not line:
        raise PermissionError("처리 권한이 없습니다.")

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.REJECTED
    line.comment = (comment or "")[:300]
    line.acted_at = timezone.now()
    line.save(update_fields=["decision", "comment", "acted_at"])

    doc.status = Document.Status.REJECTED
    doc.save(update_fields=["status"])

    notify_on_rejected(
        request=request,
        doc=doc,
        user=actor,
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


def _replace_lines(*, doc: Document, consultants, approvers, receivers) -> None:
    doc.lines.all().delete()

    order = 1
    for u in consultants:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.CONSULT,
            order=order,
            user=u,
        )
        order += 1

    for u in approvers:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=order,
            user=u,
        )
        order += 1

    for u in receivers:
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.RECEIVE,
            order=order,
            user=u,
        )
        order += 1


@transaction.atomic
def update_draft_document(
    *,
    doc: Document,
    actor,
    title: str,
    content: str,
    consultants,
    approvers,
    receivers,
    files,
) -> Document:
    if doc.created_by_id != actor.id and not actor.is_superuser:
        raise PermissionError("문서 수정 권한이 없습니다.")

    if doc.status != Document.Status.DRAFT:
        raise ValueError("임시 저장 문서만 수정할 수 있습니다.")

    doc.title = title
    doc.content = content
    doc.current_line_order = 1
    doc.save(update_fields=["title", "content", "current_line_order"])

    _replace_lines(
        doc=doc,
        consultants=consultants,
        approvers=approvers,
        receivers=receivers,
    )

    for f in files:
        Attachment.objects.create(document=doc, file=f, uploaded_by=actor)

    return doc


@transaction.atomic
def delete_draft_attachment(*, doc: Document, actor, attachment_id: int) -> bool:
    if doc.created_by_id != actor.id and not actor.is_superuser:
        raise PermissionError("문서 수정 권한이 없습니다.")

    if doc.status != Document.Status.DRAFT:
        raise ValueError("임시 저장 문서에서만 첨부 삭제가 가능합니다.")

    att = doc.attachments.filter(id=attachment_id).first()
    if not att:
        return False

    att.file.delete(save=False)
    att.delete()
    return True


@transaction.atomic
def withdraw_document(*, doc: Document, actor) -> Document:
    if doc.created_by_id != actor.id and not actor.is_superuser:
        raise PermissionError("문서 회수 권한이 없습니다.")

    if doc.status not in {
        Document.Status.SUBMITTED,
        Document.Status.IN_PROGRESS,
        Document.Status.REJECTED,
    }:
        raise ValueError("현재 상태에서는 회수할 수 없습니다.")

    doc.lines.update(
        decision=DocumentLine.Decision.PENDING,
        comment="",
        acted_at=None,
    )
    doc.status = Document.Status.DRAFT
    doc.current_line_order = 1
    doc.save(update_fields=["status", "current_line_order"])
    return doc


@transaction.atomic
def redraft_document(*, doc: Document, actor, request=None) -> Document:
    if doc.created_by_id != actor.id and not actor.is_superuser:
        raise PermissionError("문서 재기안 권한이 없습니다.")

    if doc.status != Document.Status.DRAFT:
        raise ValueError("임시 저장 문서만 재기안할 수 있습니다.")

    doc.lines.update(
        decision=DocumentLine.Decision.PENDING,
        comment="",
        acted_at=None,
    )
    doc.status = Document.Status.SUBMITTED
    doc.current_line_order = 1
    doc.save(update_fields=["status", "current_line_order"])

    if _has_active_lines(doc):
        _recalculate_doc_status_and_order(doc)
    else:
        doc.status = Document.Status.COMPLETED
        doc.save(update_fields=["status"])

    notify_on_submit(request=request, doc=doc, user=actor)
    return doc

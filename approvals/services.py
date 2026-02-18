from django.db import transaction
from django.utils import timezone

from .models import Document, DocumentLine, Attachment


def _active_roles():
    # 협의 → 결재 순으로 진행 (수신/열람은 완료 후)
    return [DocumentLine.Role.CONSULT, DocumentLine.Role.APPROVE]


def _next_pending_line(doc: Document):
    # 현재 current_line_order 기준으로 "협의/결재" 중 다음 대기 라인 찾기
    for role in _active_roles():
        line = doc.lines.filter(role=role, order=doc.current_line_order, decision=DocumentLine.Decision.PENDING).first()
        if line:
            return line
    return None


@transaction.atomic
def create_document_with_lines_and_files(*, creator, title, content, consultants, approvers, receivers, files):
    doc = Document.objects.create(
        title=title,
        content=content,
        created_by=creator,
        status=Document.Status.SUBMITTED,
        current_line_order=1,
    )

    order = 1
    # 협의 라인: order는 1..N (협의도 순차 처리)
    for u in consultants:
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.CONSULT, order=order, user=u)
        order += 1

    # 결재 라인: 협의 다음 order 이어서 순차 처리
    for u in approvers:
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.APPROVE, order=order, user=u)
        order += 1

    # 수신/열람 라인: 순서는 의미 없지만 order를 뒤로 붙임
    for idx, u in enumerate(receivers, start=order):
        DocumentLine.objects.create(document=doc, role=DocumentLine.Role.RECEIVE, order=idx, user=u)

    # 첨부파일
    for f in files:
        Attachment.objects.create(document=doc, file=f, uploaded_by=creator)

    # 진행중으로 전환 (협의/결재 라인이 없으면 바로 완료 처리)
    if doc.lines.filter(role__in=_active_roles()).exists():
        doc.status = Document.Status.IN_PROGRESS
    else:
        doc.status = Document.Status.COMPLETED
    doc.save()

    return doc


@transaction.atomic
def approve_or_consult(*, doc: Document, actor, comment: str = ""):
    line = _next_pending_line(doc)
    if not line:
        return doc  # 이미 끝났음

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.APPROVED
    line.comment = comment[:300]
    line.acted_at = timezone.now()
    line.save()

    # 다음 순번으로 이동
    doc.current_line_order += 1

    # 다음 대기 라인이 남아있나?
    if _next_pending_line(doc) is None:
        doc.status = Document.Status.COMPLETED
    else:
        doc.status = Document.Status.IN_PROGRESS
    doc.save()
    return doc


@transaction.atomic
def reject(*, doc: Document, actor, comment: str):
    line = _next_pending_line(doc)
    if not line:
        return doc

    if line.user_id != actor.id and not actor.is_superuser:
        raise PermissionError("처리 권한이 없습니다.")

    line.decision = DocumentLine.Decision.REJECTED
    line.comment = (comment or "")[:300]
    line.acted_at = timezone.now()
    line.save()

    doc.status = Document.Status.REJECTED
    doc.save()
    return doc


@transaction.atomic
def mark_read(*, doc: Document, actor):
    # 완료된 문서에서 수신/열람자 표시
    line = doc.lines.filter(role=DocumentLine.Role.RECEIVE, user_id=actor.id).first()
    if not line:
        return doc
    if line.decision == DocumentLine.Decision.PENDING:
        line.decision = DocumentLine.Decision.READ
        line.acted_at = timezone.now()
        line.save()
    return doc

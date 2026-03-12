# approvals/selectors.py
from django.db.models import Exists, OuterRef, Q

from .models import Document, DocumentLine


def my_documents(user):
    return Document.objects.filter(created_by=user).order_by("-id")


def inbox_pending(user):
    """
    내 처리 대기 문서함

    정책:
    1) 협의자(CONSULT)
       - 본인 협의 라인이 PENDING이면 즉시 inbox 표시
       - 협의자는 동시 승인

    2) 결재자(APPROVE)
       - 본인 결재 라인이 PENDING이어야 함
       - 남아 있는 협의 라인이 없어야 함
       - 자기보다 앞선 결재 PENDING 라인이 없어야 함
         (= 순차 결재에서 지금 내 차례여야 함)
    """
    pending_consult_for_user = DocumentLine.objects.filter(
        document_id=OuterRef("pk"),
        user=user,
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    )

    pending_approve_for_user = DocumentLine.objects.filter(
        document_id=OuterRef("pk"),
        user=user,
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
    )

    any_pending_consult = DocumentLine.objects.filter(
        document_id=OuterRef("pk"),
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    )

    earlier_pending_approve_exists = DocumentLine.objects.filter(
        document_id=OuterRef("document_id"),
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
        order__lt=OuterRef("order"),
    )

    actionable_approve_for_user = (
        DocumentLine.objects.filter(
            document_id=OuterRef("pk"),
            user=user,
            role=DocumentLine.Role.APPROVE,
            decision=DocumentLine.Decision.PENDING,
        )
        .annotate(
            has_earlier_pending_approve=Exists(earlier_pending_approve_exists),
        )
        .filter(has_earlier_pending_approve=False)
    )

    return (
        Document.objects.filter(status=Document.Status.IN_PROGRESS)
        .annotate(
            has_pending_consult_for_user=Exists(pending_consult_for_user),
            has_pending_approve_for_user=Exists(pending_approve_for_user),
            has_any_pending_consult=Exists(any_pending_consult),
            has_actionable_approve_for_user=Exists(actionable_approve_for_user),
        )
        .filter(
            Q(has_pending_consult_for_user=True)
            | Q(
                has_any_pending_consult=False,
                has_pending_approve_for_user=True,
                has_actionable_approve_for_user=True,
            )
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


def completed_docs(user):
    return (
        Document.objects.filter(status=Document.Status.COMPLETED)
        .filter(Q(created_by=user) | Q(lines__user=user))
        .distinct()
        .order_by("-id")
    )


def rejected_docs(user):
    return (
        Document.objects.filter(status=Document.Status.REJECTED)
        .filter(Q(created_by=user) | Q(lines__user=user))
        .distinct()
        .order_by("-id")
    )
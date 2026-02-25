# approvals/notify.py
from __future__ import annotations

from typing import Iterable, List, Optional, Set

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def _safe_email_list(users: Iterable) -> List[str]:
    """
    ✅ 사용자 목록에서 이메일만 안전하게 추출
    - 공백/None 제거
    - 중복 제거
    - 정렬(메일 발송 테스트/로그 보기 편함)
    """
    emails: Set[str] = set()
    for u in users or []:
        if not u:
            continue
        email = (getattr(u, "email", "") or "").strip()
        if email:
            emails.add(email)
    return sorted(emails)


def _build_doc_url(request, doc_id: int) -> str:
    """
    ✅ 문서 상세 URL을 절대경로로 생성
    - request가 있으면 build_absolute_uri 사용
    - request가 없으면 상대경로 반환(안전 fallback)
    """
    path = reverse("approvals:doc_detail", kwargs={"doc_id": doc_id})
    if request is None:
        return path
    return request.build_absolute_uri(path)


def _send(subject: str, body: str, to_emails: List[str]) -> bool:
    """
    ✅ 메일 발송 공통 처리
    - 수신자가 없으면 False
    - 예외 발생 시 False (서비스 흐름 깨지지 않게)
    """
    if not to_emails:
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(
        settings, "EMAIL_HOST_USER", ""
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=to_emails,
            fail_silently=False,  # 예외를 잡아서 False로 처리할 거라서 False 유지
        )
        return True
    except Exception:
        # 운영에서는 로깅 추가 가능:
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.exception("Email send failed")
        return False


# =========================
# ✅ 알림 함수들
# =========================

def notify_on_submit(*, doc, request=None) -> bool:
    """
    상신 시:
    - 협의자 + 결재자에게 알림
    """
    doc_url = _build_doc_url(request, doc.id)

    # lines에서 role 기반으로 대상 추출 (doc.lines는 DocumentLine 쿼리셋)
    consultants = [ln.user for ln in doc.lines.filter(role="CONSULT").select_related("user")]
    approvers = [ln.user for ln in doc.lines.filter(role="APPROVE").select_related("user")]

    to_emails = _safe_email_list(list(consultants) + list(approvers))

    subject = f"[전자결재] 상신: {doc.title}"
    body = "\n".join(
        [
            f"문서가 상신되었습니다.",
            f"- 문서번호: {doc.id}",
            f"- 제목: {doc.title}",
            "",
            f"문서 보기: {doc_url}",
        ]
    )
    return _send(subject, body, to_emails)


def notify_on_line_approved(*, doc, actor, request=None) -> bool:
    """
    결재/협의 승인 처리 후:
    - 다음 처리자(현재 current_line_order의 PENDING)에게 알림
    - 만약 완료되었으면 완료 알림으로 notify_on_completed() 호출
    """
    # 완료면 완료 알림
    if getattr(doc, "status", None) == "COMPLETED":
        return notify_on_completed(doc=doc, request=request)

    # 다음 처리자 찾기
    next_line = doc.lines.filter(
        order=doc.current_line_order,
        decision="PENDING",
        role__in=["CONSULT", "APPROVE"],
    ).select_related("user").first()

    if not next_line:
        # 다음 라인이 없는데 status가 COMPLETED가 아닌 경우도 있을 수 있으므로 안전하게 완료 알림 시도
        return notify_on_completed(doc=doc, request=request)

    doc_url = _build_doc_url(request, doc.id)
    to_emails = _safe_email_list([next_line.user])

    subject = f"[전자결재] 처리 요청: {doc.title}"
    body = "\n".join(
        [
            f"결재(또는 협의) 처리 요청이 도착했습니다.",
            f"- 문서번호: {doc.id}",
            f"- 제목: {doc.title}",
            f"- 현재순서: {doc.current_line_order}",
            "",
            f"문서 보기: {doc_url}",
        ]
    )
    return _send(subject, body, to_emails)


def notify_on_rejected(*, doc, actor, comment: str, request=None) -> bool:
    """
    반려 시:
    - 상신자(created_by)에게 알림
    """
    doc_url = _build_doc_url(request, doc.id)
    to_emails = _safe_email_list([doc.created_by])

    subject = f"[전자결재] 반려: {doc.title}"
    body = "\n".join(
        [
            f"문서가 반려되었습니다.",
            f"- 문서번호: {doc.id}",
            f"- 제목: {doc.title}",
            f"- 반려자: {getattr(actor, 'username', '')}",
            f"- 반려사유: {comment}",
            "",
            f"문서 보기: {doc_url}",
        ]
    )
    return _send(subject, body, to_emails)


def notify_on_completed(*, doc, request=None) -> bool:
    """
    결재 완료 시:
    - 상신자 + 협의자 + 결재자 + 수신자에게 알림
    """
    doc_url = _build_doc_url(request, doc.id)

    # 전체 라인 사용자 + 상신자
    line_users = [ln.user for ln in doc.lines.all().select_related("user")]
    all_targets = [doc.created_by] + list(line_users)

    to_emails = _safe_email_list(all_targets)

    subject = f"[전자결재] 완료: {doc.title}"
    body = "\n".join(
        [
            f"문서 결재가 완료되었습니다.",
            f"- 문서번호: {doc.id}",
            f"- 제목: {doc.title}",
            "",
            f"문서 보기: {doc_url}",
        ]
    )
    return _send(subject, body, to_emails)
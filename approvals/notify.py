# approvals/notify.py
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterable

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.html import strip_tags

from .models import Document, DocumentLine


@dataclass(frozen=True)
class Recipient:
    user: object
    email: str


def _get_user_email(user) -> str:
    if not user:
        return ""
    return (getattr(user, "email", "") or "").strip()


def _iter_recipients(users: Iterable[object]) -> list[Recipient]:
    recips: list[Recipient] = []
    for u in users:
        email = _get_user_email(u)
        if email:
            recips.append(Recipient(user=u, email=email))

    # 이메일 중복 제거
    seen: set[str] = set()
    uniq: list[Recipient] = []
    for r in recips:
        if r.email in seen:
            continue
        seen.add(r.email)
        uniq.append(r)
    return uniq


def _doc_url(doc: Document, request=None) -> str:
    # URLconf 기준으로 상세 URL 생성
    path = reverse("approvals:doc_detail", kwargs={"doc_id": doc.pk})

    # request 있으면 절대 URL로
    if request:
        return request.build_absolute_uri(path)

    # request 없으면 settings의 SITE_BASE_URL 사용
    base = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}{path}"


def _toast(request, level: str, text: str) -> None:
    if not request:
        return
    fn = {
        "success": messages.success,
        "info": messages.info,
        "warning": messages.warning,
        "error": messages.error,
    }.get(level, messages.info)
    fn(request, text)


def _send_email(subject: str, body: str, to_emails: list[str]) -> None:
    if not to_emails:
        return

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not from_email:
        return

    def _job() -> None:
        try:
            send_mail(
                subject=subject,
                message=strip_tags(body),
                from_email=from_email,
                recipient_list=to_emails,
                fail_silently=True,
            )
        except Exception:
            # 알림 실패가 결재 플로우를 막지 않도록 무시
            pass

    # 요청 응답을 막지 않도록 백그라운드로 발송
    threading.Thread(target=_job, daemon=True).start()


def _active_roles():
    return [DocumentLine.Role.CONSULT, DocumentLine.Role.APPROVE]


def _pending_active_lines(doc: Document):
    return doc.lines.filter(
        role__in=_active_roles(),
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order")


def _current_pending_line(doc: Document):
    return doc.lines.filter(
        role__in=_active_roles(),
        order=doc.current_line_order,
        decision=DocumentLine.Decision.PENDING,
    ).first()


def notify_on_submit(*, request=None, doc: Document, user=None) -> None:
    """
    상신 알림: 협의자+결재자(활성 라인)의 '전체'에게 알림.
    """
    url = _doc_url(doc, request=request)
    pending = _pending_active_lines(doc)
    recipients = _iter_recipients([ln.user for ln in pending])

    subject = f"[전자결재] 상신: {doc.title}"
    body = f"문서가 상신되었습니다.\n\n제목: {doc.title}\n링크: {url}"

    _toast(request, "info", f"상신 처리되었습니다. ({doc.title})")
    _send_email(subject, body, [r.email for r in recipients])


def notify_on_line_approved(*, request=None, doc: Document, user) -> None:
    """
    라인 승인/협의 완료 알림:
    - 다음 처리자(다음 pending 라인)에게 알림
    - 다음 라인이 없으면 완료 알림(상신자)
    """
    url = _doc_url(doc, request=request)
    next_line = _current_pending_line(doc)

    actor_name = (
        getattr(user, "get_full_name", lambda: "")()  # type: ignore[misc]
        or getattr(user, "username", "")
        or "처리자"
    )

    if next_line:
        recipients = _iter_recipients([next_line.user])
        subject = f"[전자결재] 처리 요청: {doc.title}"
        body = (
            f"이전 단계가 처리되었습니다.\n\n"
            f"문서: {doc.title}\n"
            f"처리자: {actor_name}\n"
            f"다음 처리자: {getattr(next_line.user, 'username', '')}\n"
            f"링크: {url}"
        )
        _toast(request, "info", f"다음 처리자에게 알림을 보냈습니다. ({doc.title})")
        _send_email(subject, body, [r.email for r in recipients])
        return

    # 완료면 상신자에게 완료 알림
    notify_on_completed(request=request, doc=doc, user=getattr(doc, "created_by", None))


def notify_on_completed(*, request=None, doc: Document, user=None) -> None:
    """
    완료 알림: 기본은 상신자(creator)에게.
    user를 넘기면 그 사용자에게도/또는 대체로 보낼 수 있음.
    """
    url = _doc_url(doc, request=request)

    target = user or getattr(doc, "created_by", None)
    recipients = _iter_recipients([target] if target else [])

    subject = f"[전자결재] 완료: {doc.title}"
    body = f"문서가 완료되었습니다.\n\n제목: {doc.title}\n링크: {url}"

    _toast(request, "success", f"문서가 완료되었습니다. ({doc.title})")
    _send_email(subject, body, [r.email for r in recipients])


def notify_on_rejected(*, request=None, doc: Document, user, reason: str) -> None:
    """
    반려 알림: 기본은 상신자(created_by)에게.
    """
    url = _doc_url(doc, request=request)
    reason = (reason or "").strip()

    creator = getattr(doc, "created_by", None)
    recipients = _iter_recipients([creator] if creator else [])

    subject = f"[전자결재] 반려: {doc.title}"
    body = f"문서가 반려되었습니다.\n\n제목: {doc.title}\n사유: {reason}\n링크: {url}"

    _toast(request, "error", f"문서가 반려되었습니다. ({doc.title})")
    _send_email(subject, body, [r.email for r in recipients])
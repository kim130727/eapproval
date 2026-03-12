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


def _display_name(user) -> str:
    """
    표시 이름 우선순위:
    1) user.profile.display_name()
    2) user.profile.full_name
    3) user.get_full_name()
    4) user.username
    """
    if not user:
        return "사용자"

    profile = getattr(user, "profile", None)
    if profile and hasattr(profile, "display_name"):
        try:
            v = profile.display_name()
            if v:
                return v
        except Exception:
            pass

    if profile and getattr(profile, "full_name", ""):
        v = (profile.full_name or "").strip()
        if v:
            return v

    if hasattr(user, "get_full_name"):
        v = (user.get_full_name() or "").strip()
        if v:
            return v

    return (getattr(user, "username", "") or "사용자").strip()


def _get_user_email(user) -> str:
    if not user:
        return ""
    return (getattr(user, "email", "") or "").strip()


def _iter_recipients(users: Iterable[object]) -> list[Recipient]:
    recips: list[Recipient] = []
    for u in users:
        if not u:
            continue
        email = _get_user_email(u)
        if email:
            recips.append(Recipient(user=u, email=email))

    seen: set[str] = set()
    uniq: list[Recipient] = []
    for r in recips:
        if r.email in seen:
            continue
        seen.add(r.email)
        uniq.append(r)
    return uniq


def _doc_url(doc: Document, request=None) -> str:
    path = reverse("approvals:doc_detail", kwargs={"doc_id": doc.pk})

    if request:
        return request.build_absolute_uri(path)

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
            pass

    threading.Thread(target=_job, daemon=True).start()


def _pending_consult_lines(doc: Document):
    return doc.lines.filter(
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")


def _pending_approve_lines(doc: Document):
    return doc.lines.filter(
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")


def _current_pending_approve_line(doc: Document):
    return _pending_approve_lines(doc).first()


def _receive_lines(doc: Document):
    return doc.lines.filter(role=DocumentLine.Role.RECEIVE).order_by("order", "id")


def notify_on_submit(*, request=None, doc: Document, user=None) -> None:
    """
    상신 시 알림 정책:
    1) 협의자가 있으면 협의자 전체에게 알림
    2) 협의자가 없고 결재자가 있으면 첫 결재자에게 알림
    3) 둘 다 없으면 완료 알림
    """
    url = _doc_url(doc, request=request)
    creator_name = _display_name(getattr(doc, "created_by", None))

    pending_consults = _pending_consult_lines(doc)
    if pending_consults.exists():
        recipients = _iter_recipients([ln.user for ln in pending_consults])

        subject = f"[전자결재] 협의 요청: {doc.title}"
        body = (
            f"문서가 상신되어 협의가 시작되었습니다.\n\n"
            f"제목: {doc.title}\n"
            f"상신자: {creator_name}\n"
            f"처리 단계: 협의\n"
            f"링크: {url}"
        )

        _toast(request, "info", f"상신 처리되었습니다. 협의자들에게 알림을 보냈습니다. ({doc.title})")
        _send_email(subject, body, [r.email for r in recipients])
        return

    next_approve = _current_pending_approve_line(doc)
    if next_approve:
        recipients = _iter_recipients([next_approve.user])
        next_name = _display_name(next_approve.user)

        subject = f"[전자결재] 결재 요청: {doc.title}"
        body = (
            f"문서가 상신되어 결재가 시작되었습니다.\n\n"
            f"제목: {doc.title}\n"
            f"상신자: {creator_name}\n"
            f"현재 결재자: {next_name}\n"
            f"링크: {url}"
        )

        _toast(request, "info", f"상신 처리되었습니다. 첫 결재자에게 알림을 보냈습니다. ({doc.title})")
        _send_email(subject, body, [r.email for r in recipients])
        return

    notify_on_completed(request=request, doc=doc, user=getattr(doc, "created_by", None))


def notify_on_line_approved(*, request=None, doc: Document, user) -> None:
    """
    승인/협의 완료 후 알림 정책:
    1) 아직 협의가 남아 있으면 추가 알림 없음
       (남은 협의자들은 이미 상신 시 안내받음)
    2) 협의가 모두 끝났고 결재자가 남아 있으면 첫/다음 결재자에게 알림
    3) 더 이상 처리자가 없으면 완료 알림
    """
    url = _doc_url(doc, request=request)
    actor_name = _display_name(user)

    pending_consults = _pending_consult_lines(doc)
    if pending_consults.exists():
        remaining_count = pending_consults.count()
        _toast(
            request,
            "info",
            f"처리되었습니다. 남은 협의자 {remaining_count}명이 있습니다. ({doc.title})",
        )
        return

    next_line = _current_pending_approve_line(doc)
    if next_line:
        recipients = _iter_recipients([next_line.user])
        next_name = _display_name(next_line.user)

        subject = f"[전자결재] 처리 요청: {doc.title}"
        body = (
            f"이전 단계가 처리되었습니다.\n\n"
            f"문서: {doc.title}\n"
            f"처리자: {actor_name}\n"
            f"현재 단계: 결재\n"
            f"다음 처리자: {next_name}\n"
            f"링크: {url}"
        )

        _toast(request, "info", f"다음 결재자에게 알림을 보냈습니다. ({doc.title})")
        _send_email(subject, body, [r.email for r in recipients])
        return

    notify_on_completed(request=request, doc=doc, user=getattr(doc, "created_by", None))


def notify_on_completed(*, request=None, doc: Document, user=None) -> None:
    """
    완료 알림:
    - 기본은 상신자에게 발송
    - 수신자가 있으면 함께 안내 가능
    """
    url = _doc_url(doc, request=request)

    creator = getattr(doc, "created_by", None)
    target = user or creator
    receive_users = [ln.user for ln in _receive_lines(doc)]
    recipients = _iter_recipients(([target] if target else []) + receive_users)

    creator_name = _display_name(creator)

    subject = f"[전자결재] 완료: {doc.title}"
    body = (
        f"문서가 완료되었습니다.\n\n"
        f"제목: {doc.title}\n"
        f"상신자: {creator_name}\n"
        f"링크: {url}"
    )

    _toast(request, "success", f"문서가 완료되었습니다. ({doc.title})")
    _send_email(subject, body, [r.email for r in recipients])


def notify_on_rejected(*, request=None, doc: Document, user, reason: str) -> None:
    """
    반려 알림:
    - 기본은 상신자에게 발송
    """
    url = _doc_url(doc, request=request)
    reason = (reason or "").strip()

    creator = getattr(doc, "created_by", None)
    recipients = _iter_recipients([creator] if creator else [])

    actor_name = _display_name(user)
    creator_name = _display_name(creator)

    subject = f"[전자결재] 반려: {doc.title}"
    body = (
        f"문서가 반려되었습니다.\n\n"
        f"제목: {doc.title}\n"
        f"상신자: {creator_name}\n"
        f"반려 처리자: {actor_name}\n"
        f"사유: {reason}\n"
        f"링크: {url}"
    )

    _toast(request, "error", f"문서가 반려되었습니다. ({doc.title})")
    _send_email(subject, body, [r.email for r in recipients])
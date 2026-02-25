from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def _build_doc_url(request, doc_id: int) -> str:
    """
    문서 상세 URL 생성

    우선순위:
    1) request 존재 -> request.build_absolute_uri()
    2) request 없음 -> settings.SITE_BASE_URL 사용
    3) SITE_BASE_URL 없음 -> 상대경로 반환
    """
    path = reverse("approvals:doc_detail", args=[doc_id])

    if request is not None:
        return request.build_absolute_uri(path)

    base_url = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}{path}"

    return path


def _send_mail(to_email: str, subject: str, body: str) -> None:
    if not to_email:
        return

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=True,
    )


def _safe_title(doc) -> str:
    return getattr(doc, "title", "") or getattr(doc, "subject", "") or f"문서#{getattr(doc, 'id', '')}"


def _pick_user_email(user) -> str:
    return getattr(user, "email", "") or ""


def send_document_notification(request, doc, user, subject: str, message: str) -> None:
    doc_url = _build_doc_url(request, doc.id)
    body = f"{message}\n\n문서 보기:\n{doc_url}"
    _send_mail(_pick_user_email(user), subject, body)


# ============================================================
# ✅ services.py 호환 wrapper 들 (ImportError 방지용)
# ============================================================

def notify_on_created(request, doc, user) -> None:
    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 결재 문서가 등록되었습니다",
        message=f"문서 '{_safe_title(doc)}'가 등록되었습니다.",
    )


def notify_on_completed(request, doc, user=None) -> None:
    """
    기존 코드에서 user를 안 넘길 수도 있어서, doc에서 후보를 찾아봅니다.
    프로젝트 모델 필드명에 맞게 created_by/requester 등을 조정 가능.
    """
    target = user or getattr(doc, "created_by", None) or getattr(doc, "requester", None)
    if not target:
        return

    send_document_notification(
        request=request,
        doc=doc,
        user=target,
        subject="[전자결재] 결재가 완료되었습니다",
        message=f"문서 '{_safe_title(doc)}' 결재가 완료되었습니다.",
    )


def notify_on_approved(request, doc, user) -> None:
    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 결재가 승인되었습니다",
        message=f"문서 '{_safe_title(doc)}'가 승인되었습니다.",
    )


def notify_on_rejected(request, doc, user, reason: str = "") -> None:
    extra = f"\n반려 사유: {reason}" if reason else ""
    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 결재가 반려되었습니다",
        message=f"문서 '{_safe_title(doc)}'가 반려되었습니다.{extra}",
    )


def notify_on_line_requested(request, doc, user, line=None) -> None:
    """
    결재 라인(승인자)에게 '승인 요청' 알림
    line 인자가 있으면 몇 번째 라인인지 등 메시지에 넣을 수 있습니다.
    """
    line_info = ""
    if line is not None:
        # line.order, line.step 같은게 있으면 자동 반영
        order = getattr(line, "order", None) or getattr(line, "step", None)
        if order is not None:
            line_info = f" (결재라인 {order})"

    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 결재 승인 요청",
        message=f"문서 '{_safe_title(doc)}'{line_info} 승인 요청이 도착했습니다.",
    )


def notify_on_line_approved(request, doc, line=None, actor=None, **kwargs) -> None:
    """
    결재라인 승인 알림.
    - 어떤 호출 경로는 (request, doc, line, actor=...) 로 호출
    - 어떤 호출 경로는 (request, doc, actor=...) 처럼 line 없이 호출
    따라서 line을 optional로 둡니다.
    """
    # actor fallback
    if actor is None:
        actor = getattr(request, "user", None)

    actor_name = ""
    if actor:
        actor_name = (actor.get_full_name() or "").strip() or getattr(actor, "username", "")

    # line 정보가 없을 수도 있으니 안전 처리
    order_txt = ""
    if line is not None:
        order = getattr(line, "order", None) or getattr(line, "step", None)
        if order is not None:
            order_txt = f" (라인 {order})"

    send_document_notification(
        request=request,
        doc=doc,
        user=actor or getattr(doc, "created_by", None),
        subject="[전자결재] 결재 승인",
        message=f"문서 '{_safe_title(doc)}'이(가) 승인되었습니다{order_txt}. 승인자: {actor_name}".strip(),
    )


def notify_on_line_rejected(request, doc, user, line=None, reason: str = "") -> None:
    line_info = ""
    if line is not None:
        order = getattr(line, "order", None) or getattr(line, "step", None)
        if order is not None:
            line_info = f" (결재라인 {order})"

    extra = f"\n반려 사유: {reason}" if reason else ""
    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 결재 라인 반려",
        message=f"문서 '{_safe_title(doc)}'{line_info}이(가) 반려되었습니다.{extra}",
    )

def notify_on_submit(request, doc, user=None, line=None) -> None:
    """
    문서 '제출(상신)' 시 알림.
    - services.py가 user를 안 넘겨도 동작하도록 user를 optional로 둡니다.
    - user가 없으면 doc의 작성자 계열 필드에서 추론합니다.
    """
    # 1) user fallback
    if user is None:
        user = getattr(doc, "created_by", None) or getattr(doc, "owner", None) or getattr(doc, "user", None)

    # user를 끝내 못 찾으면(모델 구조가 다른 경우) 조용히 종료하거나, 예외를 내도 됩니다.
    if user is None:
        return

    line_info = ""
    if line is not None:
        order = getattr(line, "order", None) or getattr(line, "step", None)
        if order is not None:
            line_info = f" (결재라인 {order})"

    send_document_notification(
        request=request,
        doc=doc,
        user=user,
        subject="[전자결재] 문서가 제출되었습니다",
        message=f"문서 '{_safe_title(doc)}'{line_info}가 제출(상신)되었습니다.",
    )
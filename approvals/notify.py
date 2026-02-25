# approvals/notify.py

from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail


def _build_doc_url(request, doc_id):
    """
    문서 상세 URL 생성

    우선순위:
    1️⃣ request 존재 → request.build_absolute_uri()
    2️⃣ request 없음 → settings.SITE_BASE_URL 사용
    3️⃣ SITE_BASE_URL 없음 → 상대경로 반환 (최후 fallback)
    """

    path = reverse("approvals:doc_detail", args=[doc_id])

    # ✔ 일반 웹 요청 (가장 정상적인 경우)
    if request is not None:
        return request.build_absolute_uri(path)

    # ✔ request 없는 경우 (admin action / shell / async 등)
    base_url = getattr(settings, "SITE_BASE_URL", "").rstrip("/")

    if base_url:
        return f"{base_url}{path}"

    # ✔ 최후 fallback (상대경로)
    return path


def send_document_notification(request, doc, user, subject, message):
    """
    결재 알림 메일 발송
    """

    if not user.email:
        return

    doc_url = _build_doc_url(request, doc.id)

    full_message = f"{message}\n\n문서 보기:\n{doc_url}"

    send_mail(
        subject=subject,
        message=full_message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )
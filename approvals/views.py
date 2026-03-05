# approvals/views.py
import csv
import io
import os
import zipfile

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import smart_str

from accounts.utils import sync_profile_role_from_groups
from .forms import DocumentForm
from .models import Attachment, Document
from .permissions import CHAIR_GROUP, can_view_document, is_chair
from .selectors import inbox_pending, my_documents, received_docs, completed_docs, rejected_docs
from .services import approve_or_consult, create_document_with_lines_and_files, mark_read, reject

User = get_user_model()


def _display_name(user) -> str:
    """
    ✅ 화면/내보내기 표시용 이름: Profile > full_name > username
    """
    if not user:
        return "-"

    profile = getattr(user, "profile", None)
    if profile:
        # 1) profile.display_name() 존재하면 최우선
        disp = getattr(profile, "display_name", None)
        if callable(disp):
            name = disp()
            if name:
                return str(name).strip()

        # 2) profile.name / profile.full_name 등 흔한 필드 fallback
        for attr in ("name", "full_name", "real_name", "nickname"):
            v = getattr(profile, attr, None)
            if v:
                v = str(v).strip()
                if v:
                    return v

    # 3) User.get_full_name()
    get_full = getattr(user, "get_full_name", None)
    if callable(get_full):
        full = (get_full() or "").strip()
        if full:
            return full

    # 4) username / email
    return (getattr(user, "username", "") or getattr(user, "email", "") or "-").strip() or "-"


@login_required
def home(request):
    ctx = {
        "my_count": my_documents(request.user).count(),
        "inbox_count": inbox_pending(request.user).count(),
        "recv_count": received_docs(request.user).count(),
    }
    return render(request, "approvals/home.html", ctx)


@login_required
def doc_list(request):
    docs = my_documents(request.user)
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "내 문서함",
            "docs": docs,
            # ✅ 템플릿은 아래 2개를 사용해서 URL을 구성해야 합니다.
            #    {% url csv_export_url kind=csv_kind %}  (혹은 kind 자리에 csv_kind)
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "my",
        },
    )


@login_required
def inbox(request):
    docs = inbox_pending(request.user)
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "결재함(내 처리 대기)",
            "docs": docs,
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "inbox",
        },
    )


@login_required
def received_list(request):
    docs = received_docs(request.user)
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "수신/열람함",
            "docs": docs,
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "received",
        },
    )


@login_required
def completed_list(request):
    docs = completed_docs(request.user)
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "완료함",
            "docs": docs,
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "completed",
        },
    )


@login_required
def rejected_list(request):
    docs = rejected_docs(request.user)
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "반려함",
            "docs": docs,
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "rejected",
        },
    )


@login_required
def export_docs_csv(request, kind: str):
    """
    ✅ 각 문서함 화면에서 CSV로 저장
    kind: my | inbox | received | completed | rejected
    URL: approvals/docs/export/<str:kind>.csv
    """
    kind = (kind or "").strip().lower()

    if kind == "my":
        qs = my_documents(request.user)
        title = "my_documents"
    elif kind == "inbox":
        qs = inbox_pending(request.user)
        title = "inbox"
    elif kind == "received":
        qs = received_docs(request.user)
        title = "received"
    elif kind == "completed":
        qs = completed_docs(request.user)
        title = "completed"
    elif kind == "rejected":
        qs = rejected_docs(request.user)
        title = "rejected"
    else:
        raise Http404

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "status", "title", "created_by", "current_line_order", "created_at", "updated_at"])

    for d in qs:
        created_at = getattr(d, "created_at", None)
        updated_at = getattr(d, "updated_at", None)
        w.writerow(
            [
                d.id,
                d.get_status_display() if hasattr(d, "get_status_display") else getattr(d, "status", ""),
                getattr(d, "title", ""),
                _display_name(getattr(d, "created_by", None)),
                getattr(d, "current_line_order", ""),
                timezone.localtime(created_at).strftime("%Y-%m-%d %H:%M") if created_at else "",
                timezone.localtime(updated_at).strftime("%Y-%m-%d %H:%M") if updated_at else "",
            ]
        )

    content = buf.getvalue().encode("utf-8-sig")  # ✅ 엑셀 호환 BOM
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    ts = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")
    resp["Content-Disposition"] = f'attachment; filename="{title}_{ts}.csv"'
    return resp


@login_required
def doc_detail(request, doc_id: int):
    doc = get_object_or_404(Document, id=doc_id)
    if not can_view_document(request.user, doc):
        raise Http404

    # 완료 문서는 상세 들어올 때 수신/열람 처리
    if doc.status == Document.Status.COMPLETED:
        mark_read(doc=doc, actor=request.user)

    current_line = doc.lines.filter(order=doc.current_line_order, decision="PENDING").first()
    can_act = bool(current_line) and (current_line.user_id == request.user.id or request.user.is_superuser)

    return render(
        request,
        "approvals/doc_detail.html",
        {"doc": doc, "current_line": current_line, "can_act": can_act},
    )


@login_required
def doc_create(request):
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            token = (form.cleaned_data.get("submit_token") or "").strip()
            processed = request.session.get("processed_submit_tokens", {})

            # ✅ 이미 처리된 토큰이면: 중복 생성 방지
            if token and token in processed:
                return redirect("approvals:doc_detail", doc_id=processed[token])

            consultants = form.cleaned_data.get("consultants") or []
            receivers = form.cleaned_data.get("receivers") or []

            doc = create_document_with_lines_and_files(
                creator=request.user,
                title=form.cleaned_data["title"],
                content=form.cleaned_data["content"],
                consultants=consultants,
                approvers=list(form.cleaned_data["approvers"]),  # ✅ 결재자는 필수
                receivers=receivers,
                files=form.cleaned_data["files"],
                request=request,  # ✅ 이메일/알림에 absolute url 생성용
            )

            # ✅ 토큰 기록(세션)
            if token:
                processed[token] = doc.id
                if len(processed) > 30:
                    processed = dict(list(processed.items())[-30:])
                request.session["processed_submit_tokens"] = processed

            messages.success(request, "상신되었습니다.")
            return redirect("approvals:doc_detail", doc_id=doc.id)
    else:
        form = DocumentForm()

    return render(request, "approvals/doc_create.html", {"form": form})


@login_required
def act_approve(request, doc_id: int):
    doc = get_object_or_404(Document, id=doc_id)
    if request.method != "POST":
        return redirect("approvals:doc_detail", doc_id=doc.id)

    comment = request.POST.get("comment", "")

    try:
        # ✅ 규칙: 협의 라인이 존재하면(= CONSULT 라인) 협의가 모두 끝나야 결재 승인 가능
        current_line = doc.lines.filter(order=doc.current_line_order, decision="PENDING").first()
        if current_line and getattr(current_line, "role", None) == "APPROVE":
            has_pending_consult = doc.lines.filter(role="CONSULT", decision="PENDING").exists()
            if has_pending_consult:
                messages.error(request, "협의가 완료되지 않아 결재할 수 없습니다. (협의자 처리 후 결재 가능합니다)")
                return redirect("approvals:doc_detail", doc_id=doc.id)

        approve_or_consult(
            doc=doc,
            actor=request.user,
            comment=comment,
            request=request,  # ✅ 다음 처리자/완료 알림 이메일 URL
        )
        messages.success(request, "승인(또는 협의 완료) 처리했습니다.")
    except PermissionError:
        messages.error(request, "권한이 없습니다.")

    return redirect("approvals:doc_detail", doc_id=doc.id)


@login_required
def act_reject(request, doc_id: int):
    doc = get_object_or_404(Document, id=doc_id)
    if request.method != "POST":
        return redirect("approvals:doc_detail", doc_id=doc.id)

    comment = request.POST.get("comment", "")
    if not comment.strip():
        messages.error(request, "반려 사유를 입력해주세요.")
        return redirect("approvals:doc_detail", doc_id=doc.id)

    try:
        reject(
            doc=doc,
            actor=request.user,
            comment=comment,
            request=request,  # ✅ 반려 알림 이메일 URL
        )
        messages.success(request, "반려 처리했습니다.")
    except PermissionError:
        messages.error(request, "권한이 없습니다.")

    return redirect("approvals:doc_detail", doc_id=doc.id)


@login_required
def admin_chair(request):
    if not is_chair(request.user):
        raise Http404

    chair_group, _ = Group.objects.get_or_create(name=CHAIR_GROUP)

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        action = request.POST.get("action")
        if not user_id or action not in {"add", "remove"}:
            messages.error(request, "잘못된 요청입니다.")
            return redirect("approvals:admin_chair")

        target = get_object_or_404(User, id=user_id)

        if action == "add":
            target.groups.add(chair_group)
            messages.success(request, f"{_display_name(target)} 님을 위원장으로 임명했습니다.")
        else:
            target.groups.remove(chair_group)
            messages.success(request, f"{_display_name(target)} 님의 위원장 권한을 해제했습니다.")

        # ✅ role 캐시 동기화(그룹이 단일 기준)
        sync_profile_role_from_groups(target)

        return redirect("approvals:admin_chair")

    users = User.objects.all().order_by("username")
    chairs = chair_group.user_set.all().order_by("username")
    return render(
        request,
        "approvals/admin_chair.html",
        {"users": users, "chairs": chairs, "chair_group": chair_group},
    )


@login_required
def attachment_download(request, attachment_id: int):
    att = get_object_or_404(Attachment, id=attachment_id)
    if not can_view_document(request.user, att.document):
        raise Http404

    file_handle = att.file.open("rb")
    filename = os.path.basename(att.file.name)
    return FileResponse(file_handle, as_attachment=True, filename=smart_str(filename))


@login_required
def attachments_zip(request, doc_id: int):
    """
    ✅ Attachments를 zip으로 전체 저장
    """
    doc = get_object_or_404(Document, id=doc_id)
    if not can_view_document(request.user, doc):
        raise Http404

    atts = list(doc.attachments.all())
    if not atts:
        messages.error(request, "첨부파일이 없습니다.")
        return redirect("approvals:doc_detail", doc_id=doc.id)

    mem = io.BytesIO()
    used: set[str] = set()

    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for att in atts:
            base = os.path.basename(att.file.name)
            name = base

            # 파일명 충돌 방지
            if name in used:
                root, ext = os.path.splitext(base)
                i = 2
                while True:
                    cand = f"{root} ({i}){ext}"
                    if cand not in used:
                        name = cand
                        break
                    i += 1
            used.add(name)

            with att.file.open("rb") as fh:
                zf.writestr(name, fh.read())

    mem.seek(0)
    ts = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")
    filename = f"attachments_doc{doc.id}_{ts}.zip"
    return FileResponse(mem, as_attachment=True, filename=smart_str(filename))

@login_required
def documents_export_csv(request):
    """
    ✅ 호환용(기존 템플릿에서 {% url 'approvals:documents_export_csv' %} 호출 대응)
    기본: 내 문서함(my) CSV 다운로드
    """
    return export_docs_csv(request, kind="my")
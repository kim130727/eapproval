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
from .models import Attachment, Document, DocumentLine
from .permissions import CHAIR_GROUP, can_view_document, is_chair
from .selectors import inbox_pending, my_documents, received_docs, completed_docs, rejected_docs
from .services import approve_or_consult, create_document_with_lines_and_files, mark_read, reject

User = get_user_model()


def _display_name(user) -> str:
    """
    화면/내보내기 표시용 이름: Profile > full_name > username
    """
    if not user:
        return "-"

    profile = getattr(user, "profile", None)
    if profile:
        disp = getattr(profile, "display_name", None)
        if callable(disp):
            name = disp()
            if name:
                return str(name).strip()

        for attr in ("name", "full_name", "real_name", "nickname"):
            v = getattr(profile, attr, None)
            if v:
                v = str(v).strip()
                if v:
                    return v

    get_full = getattr(user, "get_full_name", None)
    if callable(get_full):
        full = (get_full() or "").strip()
        if full:
            return full

    return (getattr(user, "username", "") or getattr(user, "email", "") or "-").strip() or "-"


def _get_current_stage_info(doc: Document, user):
    """
    현재 문서의 진행 단계를 계산하여 상세 화면용 정보를 반환한다.

    반환값:
    - current_stage: "CONSULT" | "APPROVE" | None
    - current_stage_label: "협의" | "결재" | None
    - current_lines: 현재 처리중인 라인들(QuerySet)
      * 협의 단계: pending 협의 전체
      * 결재 단계: 현재 순차 결재자 1명
    - current_line: current_lines.first()
    - can_act: 현재 사용자가 처리 가능한지
    """
    pending_consults = doc.lines.filter(
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")

    if pending_consults.exists():
        current_lines = pending_consults
        can_act = user.is_superuser or current_lines.filter(user_id=user.id).exists()
        return {
            "current_stage": "CONSULT",
            "current_stage_label": "협의",
            "current_lines": current_lines,
            "current_line": current_lines.first(),
            "can_act": can_act,
        }

    pending_approves = doc.lines.filter(
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id")

    if pending_approves.exists():
        current_line = pending_approves.first()
        current_lines = doc.lines.filter(id=current_line.id)
        can_act = user.is_superuser or current_line.user_id == user.id
        return {
            "current_stage": "APPROVE",
            "current_stage_label": "결재",
            "current_lines": current_lines,
            "current_line": current_line,
            "can_act": can_act,
        }

    return {
        "current_stage": None,
        "current_stage_label": None,
        "current_lines": doc.lines.none(),
        "current_line": None,
        "can_act": False,
    }


def _list_progress_text(doc: Document) -> str:
    """
    목록 화면용 진행 상태 요약 문구
    """
    if doc.status == Document.Status.COMPLETED:
        return "결재 완료"

    if doc.status == Document.Status.REJECTED:
        return "반려됨"

    if doc.status == Document.Status.SUBMITTED:
        return "접수됨"

    if doc.status == Document.Status.DRAFT:
        return "임시 저장"

    pending_consults = doc.lines.filter(
        role=DocumentLine.Role.CONSULT,
        decision=DocumentLine.Decision.PENDING,
    ).count()

    if pending_consults > 0:
        return f"협의 진행 중 ({pending_consults}명 대기)"

    current_approve = doc.lines.filter(
        role=DocumentLine.Role.APPROVE,
        decision=DocumentLine.Decision.PENDING,
    ).order_by("order", "id").first()

    if current_approve:
        return f"{current_approve.order}번째 결재 진행 중"

    return "진행 상태 확인 필요"


def _attach_progress_text(docs):
    """
    QuerySet/iterable의 각 문서 객체에 progress_text 속성을 붙여 템플릿에서 사용 가능하게 함
    """
    docs = list(docs)
    for doc in docs:
        doc.progress_text = _list_progress_text(doc)
    return docs


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
    docs = _attach_progress_text(my_documents(request.user))
    return render(
        request,
        "approvals/doc_list.html",
        {
            "title": "내 문서함",
            "docs": docs,
            "csv_export_url": "approvals:export_docs_csv",
            "csv_kind": "my",
        },
    )


@login_required
def inbox(request):
    docs = _attach_progress_text(inbox_pending(request.user))
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
    docs = _attach_progress_text(received_docs(request.user))
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
    docs = _attach_progress_text(completed_docs(request.user))
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
    docs = _attach_progress_text(rejected_docs(request.user))
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
    각 문서함 화면에서 CSV로 저장
    kind: my | inbox | received | completed | rejected
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

    content = buf.getvalue().encode("utf-8-sig")
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    ts = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")
    resp["Content-Disposition"] = f'attachment; filename="{title}_{ts}.csv"'
    return resp


@login_required
def doc_detail(request, doc_id: int):
    doc = get_object_or_404(Document, id=doc_id)
    if not can_view_document(request.user, doc):
        raise Http404

    if doc.status == Document.Status.COMPLETED:
        mark_read(doc=doc, actor=request.user)

    stage_info = _get_current_stage_info(doc, request.user)

    return render(
        request,
        "approvals/doc_detail.html",
        {
            "doc": doc,
            "current_stage": stage_info["current_stage"],
            "current_stage_label": stage_info["current_stage_label"],
            "current_lines": stage_info["current_lines"],
            "current_line": stage_info["current_line"],
            "can_act": stage_info["can_act"],
        },
    )


@login_required
def doc_create(request):
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            token = (form.cleaned_data.get("submit_token") or "").strip()
            processed = request.session.get("processed_submit_tokens", {})

            if token and token in processed:
                return redirect("approvals:doc_detail", doc_id=processed[token])

            consultants = form.cleaned_data.get("consultants") or []
            receivers = form.cleaned_data.get("receivers") or []

            doc = create_document_with_lines_and_files(
                creator=request.user,
                title=form.cleaned_data["title"],
                content=form.cleaned_data["content"],
                consultants=consultants,
                approvers=list(form.cleaned_data["approvers"]),
                receivers=receivers,
                files=form.cleaned_data["files"],
                request=request,
            )

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
        approve_or_consult(
            doc=doc,
            actor=request.user,
            comment=comment,
            request=request,
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
            request=request,
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
    Attachments를 zip으로 전체 저장
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
    호환용(기존 템플릿에서 {% url 'approvals:documents_export_csv' %} 호출 대응)
    기본: 내 문서함(my) CSV 다운로드
    """
    return export_docs_csv(request, kind="my")
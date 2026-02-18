from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import smart_str

import os

from .forms import DocumentForm
from .models import Attachment, Document
from .permissions import CHAIR_GROUP, can_view_document, is_chair
from .selectors import inbox_pending, my_documents, received_docs
from .services import (
    approve_or_consult,
    create_document_with_lines_and_files,
    mark_read,
    reject,
)

User = get_user_model()


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
    return render(request, "approvals/doc_list.html", {"title": "내 문서함", "docs": docs})


@login_required
def inbox(request):
    docs = inbox_pending(request.user)
    return render(request, "approvals/doc_list.html", {"title": "결재함(내 처리 대기)", "docs": docs})


@login_required
def received_list(request):
    docs = received_docs(request.user)
    return render(request, "approvals/doc_list.html", {"title": "수신/열람함", "docs": docs})


@login_required
def doc_detail(request, doc_id: int):
    doc = get_object_or_404(Document, id=doc_id)
    if not can_view_document(request.user, doc):
        raise Http404

    # 완료된 문서라면 수신자 열람 처리(자동)
    if doc.status == Document.Status.COMPLETED:
        mark_read(doc=doc, actor=request.user)

    # 현재 처리해야 하는 라인이 "내 것인지" 템플릿에서 버튼 표시용
    current_line = doc.lines.filter(order=doc.current_line_order, decision="PENDING").first()

    # ✅ 슈퍼유저도 처리 가능하게 할지 여부는 정책입니다.
    #    지금은 기존 코드 유지(슈퍼유저는 can_act True)
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
            doc = create_document_with_lines_and_files(
                creator=request.user,
                title=form.cleaned_data["title"],
                content=form.cleaned_data["content"],
                consultants=form.cleaned_data["consultants"],
                approvers=form.cleaned_data["approvers"],
                receivers=form.cleaned_data["receivers"],
                files=form.cleaned_data["files"],
            )
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
        approve_or_consult(doc=doc, actor=request.user, comment=comment)
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
        reject(doc=doc, actor=request.user, comment=comment)
        messages.success(request, "반려 처리했습니다.")
    except PermissionError:
        messages.error(request, "권한이 없습니다.")
    return redirect("approvals:doc_detail", doc_id=doc.id)


@login_required
def admin_chair(request):
    # ✅ 위원장 임명 페이지: 위원장(CHAIR)만 접근 (슈퍼유저를 포함할지 여부는 is_chair 구현에 따름)
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
            messages.success(request, f"{target.username} 님을 위원장으로 임명했습니다.")
        elif action == "remove":
            target.groups.remove(chair_group)
            messages.success(request, f"{target.username} 님의 위원장 권한을 해제했습니다.")

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

    # ✅ 문서 열람 권한 있는 사람만 다운로드
    if not can_view_document(request.user, att.document):
        raise Http404

    file_handle = att.file.open("rb")
    filename = os.path.basename(att.file.name)

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=smart_str(filename),
    )

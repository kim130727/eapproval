# approvals/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction

from accounts.models import Profile
from .models import Document, DocumentLine
from .forms import DocumentForm


# ✅ 1) 홈
@login_required
def home(request):
    return render(request, "approvals/home.html")


# ✅ 2) 문서 목록
@login_required
def doc_list(request):
    docs = Document.objects.order_by("-created_at")
    return render(request, "approvals/doc_list.html", {"docs": docs})


# ✅ 3) 받은문서함(임시)
@login_required
def inbox(request):
    """
    임시 Inbox:
    - 내가 결재/협의/수신 라인에 포함된 문서들을 보여줍니다.
    """
    doc_ids = (
        DocumentLine.objects
        .filter(user=request.user)
        .values_list("document_id", flat=True)
        .distinct()
    )
    docs = Document.objects.filter(id__in=doc_ids).order_by("-created_at")
    return render(request, "approvals/inbox.html", {"docs": docs})


# ✅ 4) 문서 생성(상신) + 위원장 자동 결재라인 생성
@login_required
@transaction.atomic
def document_create(request):
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.created_by = request.user
            document.status = "SUBMITTED"
            document.current_line_order = 1
            document.save()

            chairs = Profile.objects.filter(role=Profile.ROLE_CHAIR).select_related("user")
            if not chairs.exists():
                messages.error(request, "위원장이 설정되어 있지 않아 상신할 수 없습니다. 먼저 위원장을 지정해주세요.")
                # atomic이므로 예외를 던져 롤백되게 처리
                raise ValueError("No chair profiles found")

            order = 1
            for p in chairs:
                DocumentLine.objects.create(
                    document=document,
                    role="APPROVE",
                    order=order,
                    user=p.user,
                )
                order += 1

            messages.success(request, "문서가 상신되었습니다.")
            return redirect("approvals:doc_list")
    else:
        form = DocumentForm()

    return render(request, "approvals/document_form.html", {"form": form})


# ✅ 5) 문서 상세(임시)
@login_required
def detail(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)
    lines = DocumentLine.objects.filter(document=document).select_related("user").order_by("role", "order", "id")
    return render(request, "approvals/detail.html", {"document": document, "lines": lines})

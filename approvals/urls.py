# approvals/urls.py
from django.urls import path
from . import views

app_name = "approvals"

urlpatterns = [
    path("", views.home, name="home"),
    path("approvals/docs/", views.doc_list, name="doc_list"),
    path("approvals/inbox/", views.inbox, name="inbox"),

    # ✅ 수신/열람함 name 기준 확정: "received"
    path("approvals/received/", views.received_list, name="received"),

    # ✅ 추가 완료함 반려함
    path("approvals/completed/", views.completed_list, name="completed"),
    path("approvals/rejected/", views.rejected_list, name="rejected"),

    path("approvals/new/", views.doc_create, name="doc_create"),

    # ✅ 기존 상세
    path("approvals/<int:doc_id>/", views.doc_detail, name="doc_detail"),

    # ✅ 호환용 추가(이 한 줄)
    path("approvals/documents/<int:doc_id>/", views.doc_detail, name="doc_detail_legacy"),
    
    path("approvals/<int:doc_id>/approve/", views.act_approve, name="act_approve"),
    path("approvals/<int:doc_id>/reject/", views.act_reject, name="act_reject"),
    path("approvals/admin/chair/", views.admin_chair, name="admin_chair"),
    path(
        "approvals/attachments/<int:attachment_id>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
]

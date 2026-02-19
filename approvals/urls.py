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

    path("approvals/new/", views.doc_create, name="doc_create"),
    path("approvals/<int:doc_id>/", views.doc_detail, name="doc_detail"),
    path("approvals/<int:doc_id>/approve/", views.act_approve, name="act_approve"),
    path("approvals/<int:doc_id>/reject/", views.act_reject, name="act_reject"),
    path("approvals/admin/chair/", views.admin_chair, name="admin_chair"),
    path(
        "approvals/attachments/<int:attachment_id>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
]

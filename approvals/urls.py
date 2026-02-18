from django.urls import path
from . import views

app_name = "approvals"

urlpatterns = [
    # 메인
    path("", views.home, name="home"),

    # 문서함
    path("approvals/docs/", views.doc_list, name="doc_list"),
    path("approvals/inbox/", views.inbox, name="inbox"),
    path("approvals/received/", views.received_list, name="received_list"),

    # 문서 작성/상신
    path("approvals/new/", views.doc_create, name="doc_create"),

    # 문서 상세/처리  ✅ doc_id 필요
    path("approvals/<int:doc_id>/", views.doc_detail, name="doc_detail"),
    path("approvals/<int:doc_id>/approve/", views.act_approve, name="act_approve"),
    path("approvals/<int:doc_id>/reject/", views.act_reject, name="act_reject"),

    # 위원장 관리
    path("approvals/admin/chair/", views.admin_chair, name="admin_chair"),

    # 첨부 다운로드 ✅ attachment_id 필요
    path(
        "approvals/attachments/<int:attachment_id>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
]

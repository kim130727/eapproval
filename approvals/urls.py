# approvals/urls.py
from django.urls import path
from . import views

app_name = "approvals"

urlpatterns = [
    # 홈
    path("", views.home, name="home"),

    # 문서함 / 목록
    path("approvals/docs/", views.doc_list, name="doc_list"),

    # 보관함/함들
    path("approvals/inbox/", views.inbox, name="inbox"),

    # ✅ 수신/열람함 name 기준 확정: "received"
    path("approvals/received/", views.received_list, name="received"),

    # ✅ CSV Export (Documents 클릭 후 저장)
    # kind 예: "documents", "received", "completed", "rejected" 등 (views.export_docs_csv 구현 기준)
    path("approvals/docs/export/<str:kind>.csv", views.export_docs_csv, name="export_docs_csv"),

    # ✅ 호환용(이름만 documents_export_csv) - 템플릿 구버전 대응
    path("approvals/docs/export.csv", views.documents_export_csv, name="documents_export_csv"),

    # ✅ 완료함 / 반려함
    path("approvals/completed/", views.completed_list, name="completed"),
    path("approvals/rejected/", views.rejected_list, name="rejected"),

    # 신규 상신
    path("approvals/new/", views.doc_create, name="doc_create"),

    # 상세
    path("approvals/<int:doc_id>/", views.doc_detail, name="doc_detail"),

    # ✅ Attachments ZIP (전체 저장)
    path("approvals/<int:doc_id>/attachments.zip", views.attachments_zip, name="attachments_zip"),

    # ✅ 호환용(legacy) 상세 URL
    path("approvals/documents/<int:doc_id>/", views.doc_detail, name="doc_detail_legacy"),

    # 결재 액션
    path("approvals/<int:doc_id>/approve/", views.act_approve, name="act_approve"),
    path("approvals/<int:doc_id>/reject/", views.act_reject, name="act_reject"),

    # 관리자(의장/위원장 등)
    path("approvals/admin/chair/", views.admin_chair, name="admin_chair"),

    # 첨부 다운로드
    path(
        "approvals/attachments/<int:attachment_id>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
]
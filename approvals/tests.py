from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Attachment, Document, DocumentLine
from .permissions import CHAIR_GROUP
from .services import (
    delete_draft_attachment,
    redraft_document,
    update_draft_document,
    withdraw_document,
)

User = get_user_model()


class DocumentWithdrawRedraftTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="pw1234")
        self.approver = User.objects.create_user(username="approver", password="pw1234")
        self.other = User.objects.create_user(username="other", password="pw1234")

    def test_withdraw_sets_draft_and_resets_lines(self):
        doc = Document.objects.create(
            title="테스트",
            content="내용",
            created_by=self.creator,
            status=Document.Status.IN_PROGRESS,
            current_line_order=2,
        )
        line = DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=2,
            user=self.approver,
            decision=DocumentLine.Decision.APPROVED,
            comment="ok",
        )

        withdraw_document(doc=doc, actor=self.creator)

        doc.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.DRAFT)
        self.assertEqual(doc.current_line_order, 1)
        self.assertEqual(line.decision, DocumentLine.Decision.PENDING)
        self.assertEqual(line.comment, "")
        self.assertIsNone(line.acted_at)

    def test_withdraw_requires_owner(self):
        doc = Document.objects.create(
            title="테스트",
            content="내용",
            created_by=self.creator,
            status=Document.Status.SUBMITTED,
        )

        with self.assertRaises(PermissionError):
            withdraw_document(doc=doc, actor=self.other)

    def test_redraft_from_draft_resubmits_document(self):
        doc = Document.objects.create(
            title="테스트",
            content="내용",
            created_by=self.creator,
            status=Document.Status.DRAFT,
            current_line_order=1,
        )
        line = DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=1,
            user=self.approver,
            decision=DocumentLine.Decision.REJECTED,
            comment="reject",
        )

        redraft_document(doc=doc, actor=self.creator)

        doc.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.IN_PROGRESS)
        self.assertEqual(doc.current_line_order, 1)
        self.assertEqual(line.decision, DocumentLine.Decision.PENDING)
        self.assertEqual(line.comment, "")
        self.assertIsNone(line.acted_at)

    def test_redraft_only_for_draft(self):
        doc = Document.objects.create(
            title="테스트",
            content="내용",
            created_by=self.creator,
            status=Document.Status.IN_PROGRESS,
        )

        with self.assertRaises(ValueError):
            redraft_document(doc=doc, actor=self.creator)

    def test_update_draft_document_updates_content_and_lines(self):
        doc = Document.objects.create(
            title="기존 제목",
            content="기존 내용",
            created_by=self.creator,
            status=Document.Status.DRAFT,
        )
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=1,
            user=self.approver,
        )

        update_draft_document(
            doc=doc,
            actor=self.creator,
            title="새 제목",
            content="새 내용",
            consultants=[self.other],
            approvers=[self.approver],
            receivers=[],
            files=[],
        )

        doc.refresh_from_db()
        self.assertEqual(doc.title, "새 제목")
        self.assertEqual(doc.content, "새 내용")
        self.assertEqual(doc.lines.count(), 2)
        self.assertEqual(doc.lines.filter(role=DocumentLine.Role.CONSULT).first().user_id, self.other.id)
        self.assertEqual(doc.lines.filter(role=DocumentLine.Role.APPROVE).first().user_id, self.approver.id)

    def test_delete_draft_attachment_removes_target_file(self):
        doc = Document.objects.create(
            title="문서",
            content="내용",
            created_by=self.creator,
            status=Document.Status.DRAFT,
        )
        keep = Attachment.objects.create(
            document=doc,
            file=SimpleUploadedFile("keep.txt", b"keep"),
            uploaded_by=self.creator,
        )
        remove = Attachment.objects.create(
            document=doc,
            file=SimpleUploadedFile("remove.txt", b"remove"),
            uploaded_by=self.creator,
        )

        deleted = delete_draft_attachment(doc=doc, actor=self.creator, attachment_id=remove.id)

        self.assertTrue(deleted)
        self.assertTrue(Attachment.objects.filter(id=keep.id).exists())
        self.assertFalse(Attachment.objects.filter(id=remove.id).exists())


class DocRedraftViewActionFallbackTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username="creator2", password="pw1234")
        self.approver = User.objects.create_user(username="approver2", password="pw1234")
        chair_group, _ = Group.objects.get_or_create(name=CHAIR_GROUP)
        self.approver.groups.add(chair_group)

    def test_requested_action_redraft_resubmits_when_action_missing(self):
        doc = Document.objects.create(
            title="초안",
            content="내용",
            created_by=self.creator,
            status=Document.Status.DRAFT,
            current_line_order=1,
        )
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=1,
            user=self.approver,
        )

        self.client.login(username="creator2", password="pw1234")
        res = self.client.post(
            reverse("approvals:doc_redraft", args=[doc.id]),
            data={
                "title": "초안",
                "content": "내용",
                "approvers": [self.approver.id],
                "approvers_order": str(self.approver.id),
                "requested_action": "redraft",
            },
        )

        self.assertEqual(res.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.IN_PROGRESS)

    def test_query_requested_action_redraft_resubmits_when_post_action_missing(self):
        doc = Document.objects.create(
            title="초안2",
            content="내용2",
            created_by=self.creator,
            status=Document.Status.DRAFT,
            current_line_order=1,
        )
        DocumentLine.objects.create(
            document=doc,
            role=DocumentLine.Role.APPROVE,
            order=1,
            user=self.approver,
        )

        self.client.login(username="creator2", password="pw1234")
        res = self.client.post(
            f"{reverse('approvals:doc_redraft', args=[doc.id])}?requested_action=redraft",
            data={
                "title": "초안2",
                "content": "내용2",
                "approvers": [self.approver.id],
                "approvers_order": str(self.approver.id),
            },
        )

        self.assertEqual(res.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.IN_PROGRESS)

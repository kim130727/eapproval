# approvals/forms.py
import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Document
from .permissions import CHAIR_GROUP  # 프로젝트 표준: "CHAIR"

User = get_user_model()

# 파일 1개당 5MB 제한
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def user_label(u) -> str:
    """
    표시 이름 우선순위:
    - profile.display_name()
    - profile.full_name
    - username
    """
    profile = getattr(u, "profile", None)
    if profile and hasattr(profile, "display_name"):
        try:
            name = profile.display_name()
            if name:
                return name
        except Exception:
            pass

    if profile and getattr(profile, "full_name", ""):
        name = (profile.full_name or "").strip()
        if name:
            return name

    return u.username


def chair_users_queryset():
    """'위원장' 그룹(CHAIR_GROUP)에 속한 사용자만 반환"""
    return User.objects.filter(is_active=True, groups__name=CHAIR_GROUP).distinct()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs["multiple"] = True
        super().__init__(attrs)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []

        parent_clean = super().clean
        files = data if isinstance(data, (list, tuple)) else [data]

        cleaned_files = []
        for f in files:
            f = parent_clean(f, initial)

            if getattr(f, "size", 0) > MAX_FILE_SIZE:
                size_mb = round(f.size / 1024 / 1024, 2)
                raise ValidationError(f"[{f.name}] 파일이 5MB를 초과했습니다. (현재: {size_mb}MB)")

            cleaned_files.append(f)

        return cleaned_files


class DocumentForm(forms.ModelForm):
    submit_token = forms.CharField(required=False, widget=forms.HiddenInput)

    consultants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="협의자(여러 명 가능)",
        help_text="여러 명을 선택하면 동시에 협의가 진행됩니다.",
    )

    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="결재자(순서대로 진행)",
        help_text="체크 후 오른쪽 ↕️ 핸들을 드래그하면 결재 순서대로 저장됩니다.",
    )

    receivers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="수신/열람자(여러 명 가능)",
        help_text="문서 완료 후 열람 대상자입니다.",
    )

    approvers_order = forms.CharField(required=False, widget=forms.HiddenInput)

    files = MultipleFileField(required=False, label="첨부파일(여러 개 가능)")

    class Meta:
        model = Document
        fields = ("title", "content")
        widgets = {
            "content": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.initial.get("submit_token"):
            self.initial["submit_token"] = uuid.uuid4().hex

        chair_qs = chair_users_queryset()
        for fname in ("consultants", "approvers", "receivers"):
            field = self.fields[fname]
            field.queryset = chair_qs
            field.label_from_instance = user_label

    def _parse_order_ids(self, raw: str) -> list[int]:
        if not raw:
            return []

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        ids: list[int] = []
        for p in parts:
            if p.isdigit():
                ids.append(int(p))

        seen = set()
        dedup = []
        for i in ids:
            if i in seen:
                continue
            seen.add(i)
            dedup.append(i)
        return dedup

    def clean(self):
        """
        1) 위원장 아닌 유저 차단
        2) approvers는 선택한 순서대로 서버에서 재정렬
        """
        cleaned = super().clean()

        allowed_ids = set(chair_users_queryset().values_list("id", flat=True))

        for fname in ("consultants", "approvers", "receivers"):
            selected = cleaned.get(fname)
            if not selected:
                continue

            selected_ids = {u.id for u in selected}
            if not selected_ids.issubset(allowed_ids):
                self.add_error(fname, "위원장만 선택할 수 있습니다.")
                return cleaned

        selected_approvers = cleaned.get("approvers")
        if selected_approvers:
            selected_ids = [u.id for u in selected_approvers]
            order_ids = self._parse_order_ids(cleaned.get("approvers_order", ""))

            if order_ids:
                ordered = [i for i in order_ids if i in selected_ids]
                tail = [i for i in selected_ids if i not in ordered]
                final_ids = ordered + tail
            else:
                final_ids = selected_ids

            by_id = {u.id: u for u in selected_approvers}
            cleaned["approvers"] = [by_id[i] for i in final_ids if i in by_id]

        return cleaned

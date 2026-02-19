# approvals/forms.py
from django import forms
from django.contrib.auth import get_user_model

from .models import Document
from .permissions import CHAIR_GROUP  # 프로젝트 표준: "CHAIR"

User = get_user_model()


def user_label(u) -> str:
    """
    표시 이름 우선순위:
    - profile.display_name() (이번 수정 전제)
    - profile.full_name
    - username
    """
    profile = getattr(u, "profile", None)
    if profile and hasattr(profile, "display_name"):
        return profile.display_name()
    if profile and getattr(profile, "full_name", ""):
        return profile.full_name
    return u.username


def chair_users_queryset():
    """
    ✅ '위원장' 그룹(CHAIR_GROUP)에 속한 사용자만 반환
    """
    return User.objects.filter(is_active=True, groups__name=CHAIR_GROUP).distinct()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        parent_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [parent_clean(d, initial) for d in data]
        return [parent_clean(data, initial)]


class DocumentForm(forms.ModelForm):
    consultants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),  # __init__에서 위원장만 세팅
        required=False,
        widget=forms.SelectMultiple,
        label="협의자(여러 명 가능)",
    )
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),  # 위원장만
        required=True,
        widget=forms.SelectMultiple,
        label="결재자(순서대로 선택)",
        help_text="선택한 순서가 결재 순서입니다.",
    )
    receivers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),  # 위원장만
        required=False,
        widget=forms.SelectMultiple,
        label="수신/열람자(여러 명 가능)",
    )
    files = MultipleFileField(required=False, label="첨부파일(여러 개 가능)")

    class Meta:
        model = Document
        fields = ("title", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        chair_qs = chair_users_queryset()

        for fname in ("consultants", "approvers", "receivers"):
            field = self.fields[fname]
            field.queryset = chair_qs
            field.label_from_instance = user_label

    def clean(self):
        """
        ✅ 프론트 조작으로 위원장 아닌 유저 ID가 들어와도 서버에서 차단
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

from django import forms
from django.contrib.auth import get_user_model
from .models import Document

User = get_user_model()

def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for fname in ["consultants", "approvers", "receivers"]:
        def user_label(u):
            if hasattr(u, "profile"):
                return u.profile.full_name or u.username
            return u.username
        self.fields[fname].label_from_instance = user_label 
        self.fields[fname].widget.attrs.update({"id": f"id_{fname}"}) 

def user_label(u):
    # Profile이 있으면 이름+위원장 표기
    if hasattr(u, "profile") and hasattr(u.profile, "display_name"):
        return u.profile.display_name()
    # fallback
    return getattr(getattr(u, "profile", None), "full_name", "") or u.username


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        parent_clean = super(MultipleFileField, self).clean
        if isinstance(data, (list, tuple)):
            return [parent_clean(d, initial) for d in data]
        return [parent_clean(data, initial)]


class DocumentForm(forms.ModelForm):
    consultants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple,
        label="협의자(여러 명 가능)",
    )
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=True,
        widget=forms.SelectMultiple,
        label="결재자(순서대로 선택)",
        help_text="선택한 순서가 결재 순서입니다.",
    )
    receivers = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple,
        label="수신/열람자(여러 명 가능)",
    )

    files = MultipleFileField(
        required=False,
        label="첨부파일(여러 개 가능)",
    )

    class Meta:
        model = Document
        fields = ("title", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ 드롭다운 표시를 "이름 (위원장)"으로 변경
        for fname in ["consultants", "approvers", "receivers"]:
            self.fields[fname].label_from_instance = user_label

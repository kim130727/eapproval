from django import forms
from django.contrib.auth.models import User
from .models import Document


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True  # ✅ Django가 multiple 허용하도록


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        # 업로드 없으면 빈 리스트
        if not data:
            return []

        # ✅ super()를 먼저 고정 (listcomp 안에서 super() 꼬임 방지)
        parent_clean = super(MultipleFileField, self).clean

        # 여러 파일이면 각각 clean
        if isinstance(data, (list, tuple)):
            cleaned = []
            for d in data:
                cleaned.append(parent_clean(d, initial))
            return cleaned

        # 단일 파일이어도 리스트로 반환
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

    # ✅ 멀티 파일 업로드 필드 (Django 5 대응)
    files = MultipleFileField(
        required=False,
        label="첨부파일(여러 개 가능)",
    )

    class Meta:
        model = Document
        fields = ("title", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}

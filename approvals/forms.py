# approvals/forms.py
from django import forms
from django.contrib.auth import get_user_model

from .models import Document
from .permissions import CHAIR_GROUP  # 프로젝트 표준: "CHAIR"

User = get_user_model()


def user_label(u) -> str:
    """
    표시 이름 우선순위:
    - profile.display_name()
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
    """✅ '위원장' 그룹(CHAIR_GROUP)에 속한 사용자만 반환"""
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
        queryset=User.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="협의자(여러 명 가능)",
        help_text="체크 후 ↕️ 드래그로 순서를 바꾸면 결재 순서로 저장됩니다.",
    )
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="결재자(드래그로 순서 변경 가능)",
        help_text="체크 후 ↕️ 드래그로 순서를 바꾸면 결재 순서로 저장됩니다.",
    )   
    receivers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="수신/열람자(여러 명 가능)",
        help_text="체크 후 ↕️ 드래그로 순서를 바꾸면 결재 순서로 저장됩니다.",
    )

    # ✅ 선택 순서 저장용(프론트 JS가 콤마로 넣어줌)
    approvers_order = forms.CharField(required=False, widget=forms.HiddenInput)

    files = MultipleFileField(required=False, label="첨부파일(여러 개 가능)")

    class Meta:
        model = Document
        fields = ("title", "content")  # approvers_order는 모델필드 아님(폼만)
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        # 중복 제거(순서 유지)
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
        ✅ 1) 위원장 아닌 유저 차단(기존)
        ✅ 2) approvers는 "선택한 순서대로" 서버에서 재정렬
        """
        cleaned = super().clean()

        allowed_ids = set(chair_users_queryset().values_list("id", flat=True))

        # --- 서버단 권한 차단(기존 로직 유지) ---
        for fname in ("consultants", "approvers", "receivers"):
            selected = cleaned.get(fname)
            if not selected:
                continue
            selected_ids = {u.id for u in selected}
            if not selected_ids.issubset(allowed_ids):
                self.add_error(fname, "위원장만 선택할 수 있습니다.")
                return cleaned

        # --- ✅ approvers 순서 보장 ---
        selected_approvers = cleaned.get("approvers")
        if selected_approvers:
            selected_ids = [u.id for u in selected_approvers]

            order_ids = self._parse_order_ids(cleaned.get("approvers_order", ""))

            # order_ids가 없거나/불일치하면 -> 현재 선택 집합 기준으로 안전 fallback
            if order_ids:
                # order_ids 중에서 "실제 선택된 결재자"만 남기기
                ordered = [i for i in order_ids if i in selected_ids]

                # 사용자가 선택했는데 order_ids에 누락된 결재자는 뒤에 붙임
                tail = [i for i in selected_ids if i not in ordered]
                final_ids = ordered + tail
            else:
                final_ids = selected_ids  # fallback

            # id -> user 매핑 후 순서대로 list로 만들기
            by_id = {u.id: u for u in selected_approvers}
            cleaned["approvers"] = [by_id[i] for i in final_ids if i in by_id]

        return cleaned
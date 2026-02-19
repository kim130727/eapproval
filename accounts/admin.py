# accounts/admin.py

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "full_name")


class UserWithProfileAdminForm(forms.ModelForm):
    """
    ✅ User 변경 화면에서 Profile 필드를 User 필드처럼 보여주기 위한 폼
    - full_name, role 을 User 폼에 추가
    - 저장 시 Profile에 동기화
    """
    full_name = forms.CharField(label="이름", required=False, max_length=150)
    role = forms.ChoiceField(label="역할", required=True, choices=Profile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 기존 사용자 편집일 때: profile 값으로 초기화
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, "profile", None)
            if profile:
                self.fields["full_name"].initial = getattr(profile, "full_name", "")
                self.fields["role"].initial = getattr(profile, "role", Profile.ROLE_MEMBER)
            else:
                # 혹시 profile이 없다면 기본값
                self.fields["role"].initial = Profile.ROLE_MEMBER

    def save(self, commit=True):
        user = super().save(commit=commit)

        # ✅ Profile 동기화
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        role = self.cleaned_data.get("role") or Profile.ROLE_MEMBER

        # user 저장 후 profile update/create
        Profile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name, "role": role},
        )
        return user


# 기존 기본 User admin 제거
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    form = UserWithProfileAdminForm  # ✅ 핵심: 커스텀 폼 적용

    # ✅ inline 제거 (이제 profile은 user 폼에서 직접 수정)
    inlines = ()

    list_display = ("username", "first_name", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")

    # ✅ Personal info 바로 아래에 Profile 필드 배치
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "email")}),
        ("Profile", {"fields": ("full_name", "role")}),  # ✅ 여기!
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

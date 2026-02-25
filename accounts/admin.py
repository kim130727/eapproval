# accounts/admin.py

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile
from .utils import sync_profile_role_from_groups

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "role", "phone")
    list_filter = ("role",)
    search_fields = ("user__username", "full_name", "phone")


class UserWithProfileAdminForm(forms.ModelForm):
    """
    ✅ User 변경 화면에서 Profile.full_name만 User 필드처럼 보여주기
    ✅ email은 User 기본 필드로 그대로 저장
    - role은 '그룹 기준' 단일화로 인해 직접 수정하지 않음(자동 동기화)
    """

    full_name = forms.CharField(label="이름", required=False, max_length=150)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            profile = getattr(self.instance, "profile", None)
            if profile:
                self.fields["full_name"].initial = getattr(profile, "full_name", "")
            else:
                self.fields["full_name"].initial = ""

    def save(self, commit=True):
        user = super().save(commit=commit)

        full_name = (self.cleaned_data.get("full_name") or "").strip()
        Profile.objects.update_or_create(
            user=user,
            defaults={"full_name": full_name},
        )

        # ✅ 그룹 기준으로 role 캐시 동기화
        sync_profile_role_from_groups(user)
        return user


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    form = UserWithProfileAdminForm
    inlines = ()

    list_display = ("username", "first_name", "email", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "email", "profile__full_name")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "email")}),
        ("Profile", {"fields": ("full_name",)}),  # ✅ role 제거
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
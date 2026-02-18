from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name")
    search_fields = ("user__username", "full_name")


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


# ✅ 이미 등록돼 있으면 해제 후 다시 등록
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    inlines = (ProfileInline,)
    list_display = ("username", "profile_full_name", "is_staff", "is_superuser")

    def profile_full_name(self, obj):
        return getattr(getattr(obj, "profile", None), "full_name", "")
    profile_full_name.short_description = "이름"

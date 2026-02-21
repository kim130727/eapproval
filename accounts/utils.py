# accounts/utils.py
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

from approvals.permissions import CHAIR_GROUP  # 표준 그룹명 "CHAIR"

from .models import Profile

User = get_user_model()


def is_user_in_chair_group(user: User) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=CHAIR_GROUP).exists()


def sync_profile_role_from_groups(user: User) -> None:
    """
    ✅ 단일 기준: CHAIR_GROUP(그룹)
    - user의 그룹 상태를 기준으로 Profile.role 을 자동 동기화(캐시)
    """
    if not user or not getattr(user, "pk", None):
        return

    profile, _ = Profile.objects.get_or_create(user=user)

    # superuser는 항상 CHAIR로 표시
    desired_role = Profile.ROLE_CHAIR if (user.is_superuser or is_user_in_chair_group(user)) else Profile.ROLE_MEMBER

    if profile.role != desired_role:
        profile.role = desired_role
        profile.save(update_fields=["role"])
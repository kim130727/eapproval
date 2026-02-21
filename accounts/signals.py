# accounts/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from .models import Profile
from .utils import sync_profile_role_from_groups

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile(sender, instance: User, created: bool, **kwargs):
    """
    ✅ user 생성 시 Profile 생성
    - 이름은 first_name/username 기반 기본값 세팅
    - role은 '그룹 기준'으로 동기화
    """
    if created:
        Profile.objects.create(
            user=instance,
            full_name=(instance.first_name or instance.username),
        )
    # created 여부와 상관없이 role 동기화(안전)
    sync_profile_role_from_groups(instance)


@receiver(m2m_changed, sender=User.groups.through)
def sync_profile_role_on_group_change(sender, instance: User, action: str, **kwargs):
    """
    ✅ 그룹이 변경될 때마다 role 캐시를 동기화
    - add/remove/clear 이후에 동기화
    """
    if action in {"post_add", "post_remove", "post_clear"}:
        sync_profile_role_from_groups(instance)
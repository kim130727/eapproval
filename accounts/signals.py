# accounts/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from .models import Profile
from .utils import sync_profile_role_from_groups

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance: User, created: bool, **kwargs):
    """
    ✅ User 생성/저장 시 Profile이 없으면 생성
    - role 동기화는 아래 sync로 처리
    """
    if not instance or not instance.pk:
        return
    Profile.objects.get_or_create(user=instance)
    sync_profile_role_from_groups(instance)


@receiver(m2m_changed, sender=User.groups.through)
def sync_role_when_groups_changed(sender, instance: User, action: str, **kwargs):
    """
    ✅ User.groups 변경(add/remove/clear 등) 시 role 캐시 자동 동기화
    - Django admin / 코드 / 어디서 바꾸든 100% 반영
    """
    if action in ("post_add", "post_remove", "post_clear"):
        sync_profile_role_from_groups(instance)
#accounts/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from .models import Profile
from .utils import sync_profile_role_from_groups

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance: User, created: bool, raw=False, **kwargs):
    """
    User 생성/저장 시 Profile이 없으면 생성
    fixture loaddata 중(raw=True)에는 건너뜀
    """
    if raw:
        return
    if not instance or not instance.pk:
        return
    Profile.objects.get_or_create(user=instance)
    sync_profile_role_from_groups(instance)


@receiver(m2m_changed, sender=User.groups.through)
def sync_role_when_groups_changed(sender, instance: User, action: str, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        sync_profile_role_from_groups(instance)
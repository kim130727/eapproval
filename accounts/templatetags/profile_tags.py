# accounts/templatetags/profile_tags.py

from django import template
from django.core.exceptions import ObjectDoesNotExist

register = template.Library()


@register.filter
def display_name(user):
    """
    템플릿에서: {{ user|display_name }}
    우선순위:
    1) user.profile.display_name()
    2) user.profile.full_name
    3) user.get_full_name()
    4) user.username
    """
    if not user:
        return "-"

    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None

    if profile:
        # 1) display_name() 메서드
        try:
            fn = getattr(profile, "display_name", None)
            if callable(fn):
                name = (fn() or "").strip()
                if name:
                    return name
        except Exception:
            pass

        # 2) full_name
        name = (getattr(profile, "full_name", "") or "").strip()
        if name:
            return name

    # 3) user.get_full_name()
    try:
        name = (user.get_full_name() or "").strip()
        if name:
            return name
    except Exception:
        pass

    # 4) username
    return getattr(user, "username", "-")
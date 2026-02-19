# accounts/models.py
from django.conf import settings
from django.db import models


class Profile(models.Model):
    ROLE_MEMBER = "MEMBER"
    ROLE_CHAIR = "CHAIR"

    ROLE_CHOICES = [
        (ROLE_MEMBER, "일반회원"),
        (ROLE_CHAIR, "위원장"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150, blank=True, default="")  # ✅ 추가
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

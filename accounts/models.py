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
    full_name = models.CharField(max_length=150, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)

    def display_name(self):
        """
        화면 표시용 이름
        우선순위:
        1) full_name
        2) user.first_name
        3) username
        """
        if self.full_name and self.full_name.strip():
            return self.full_name.strip()

        if self.user.first_name and self.user.first_name.strip():
            return self.user.first_name.strip()

        return self.user.username

    def __str__(self):
        return f"{self.user.username} ({self.role})"

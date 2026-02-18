from django.conf import settings
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField("이름", max_length=50)

    def is_chair(self) -> bool:
        return self.user.groups.filter(name="CHAIR").exists() or self.user.is_superuser

    def display_name(self) -> str:
        # 이름이 없으면 username fallback
        base = self.full_name or self.user.username
        return f"{base} (위원장)" if self.is_chair() else base

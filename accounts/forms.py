# accounts/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile

User = get_user_model()


class SignupForm(UserCreationForm):
    full_name = forms.CharField(label="이름", max_length=150)
    email = forms.EmailField(label="이메일", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)

        # ✅ User.email 저장
        user.email = (self.cleaned_data.get("email") or "").strip()

        if commit:
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": (self.cleaned_data.get("full_name") or "").strip()},
            )

        return user
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

        # User.email 저장
        user.email = (self.cleaned_data.get("email") or "").strip()

        if commit:
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": (self.cleaned_data.get("full_name") or "").strip()},
            )

        return user


class ProfileUpdateForm(forms.Form):
    full_name = forms.CharField(label="이름", max_length=150, required=False)
    phone = forms.CharField(label="전화번호", max_length=20, required=False)
    email = forms.EmailField(label="이메일", required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        profile, _ = Profile.objects.get_or_create(user=self.user)

        self.fields["full_name"].initial = profile.full_name or ""
        self.fields["phone"].initial = profile.phone or ""
        self.fields["email"].initial = self.user.email or ""

    def clean_full_name(self):
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean_phone(self):
        return (self.cleaned_data.get("phone") or "").strip()

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    def save(self):
        profile, _ = Profile.objects.get_or_create(user=self.user)

        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["email"])

        profile.full_name = self.cleaned_data["full_name"]
        profile.phone = self.cleaned_data["phone"]
        profile.save(update_fields=["full_name", "phone"])

        return self.user
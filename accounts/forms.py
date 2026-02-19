from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class SignupForm(UserCreationForm):
    full_name = forms.CharField(label="이름", max_length=50)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=commit)
        # Profile은 signals에서 생성되지만, full_name은 여기서 업데이트
        if commit and hasattr(user, "profile"):
            user.profile.full_name = self.cleaned_data.get("full_name", "")
            user.profile.save(update_fields=["full_name"])
        return user

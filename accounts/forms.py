from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class SignupForm(UserCreationForm):
    full_name = forms.CharField(label="이름", max_length=50)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "password1", "password2")

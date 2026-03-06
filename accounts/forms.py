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

    pungsam_cho = forms.ChoiceField(
        label="풍삶초",
        choices=Profile.TRAINING_STATUS_CHOICES,
        required=False,
    )
    pungsam_cho_date = forms.CharField(label="풍삶초 수료일", max_length=50, required=False)

    pungsam_first = forms.ChoiceField(
        label="풍삶첫",
        choices=Profile.TRAINING_STATUS_CHOICES,
        required=False,
    )
    pungsam_first_date = forms.CharField(label="풍삶첫 수료일", max_length=50, required=False)

    pungsam_gi = forms.ChoiceField(
        label="풍삶기",
        choices=Profile.TRAINING_STATUS_CHOICES,
        required=False,
    )
    pungsam_gi_date = forms.CharField(label="풍삶기 수료일", max_length=50, required=False)

    leader_course = forms.ChoiceField(
        label="이끄미수료",
        choices=Profile.TRAINING_STATUS_CHOICES,
        required=False,
    )
    leader_course_date = forms.CharField(label="이끄미수료일", max_length=50, required=False)

    leader_status = forms.CharField(label="이끄미현황", max_length=100, required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        profile, _ = Profile.objects.get_or_create(user=self.user)

        self.fields["full_name"].initial = profile.full_name or ""
        self.fields["phone"].initial = profile.phone or ""
        self.fields["email"].initial = self.user.email or ""

        self.fields["pungsam_cho"].initial = profile.pungsam_cho or ""
        self.fields["pungsam_cho_date"].initial = profile.pungsam_cho_date or ""

        self.fields["pungsam_first"].initial = profile.pungsam_first or ""
        self.fields["pungsam_first_date"].initial = profile.pungsam_first_date or ""

        self.fields["pungsam_gi"].initial = profile.pungsam_gi or ""
        self.fields["pungsam_gi_date"].initial = profile.pungsam_gi_date or ""

        self.fields["leader_course"].initial = profile.leader_course or ""
        self.fields["leader_course_date"].initial = profile.leader_course_date or ""
        self.fields["leader_status"].initial = profile.leader_status or ""

    def clean_full_name(self):
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean_phone(self):
        return (self.cleaned_data.get("phone") or "").strip()

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    def clean_pungsam_cho_date(self):
        return (self.cleaned_data.get("pungsam_cho_date") or "").strip()

    def clean_pungsam_first_date(self):
        return (self.cleaned_data.get("pungsam_first_date") or "").strip()

    def clean_pungsam_gi_date(self):
        return (self.cleaned_data.get("pungsam_gi_date") or "").strip()

    def clean_leader_course_date(self):
        return (self.cleaned_data.get("leader_course_date") or "").strip()

    def clean_leader_status(self):
        return (self.cleaned_data.get("leader_status") or "").strip()

    def save(self):
        profile, _ = Profile.objects.get_or_create(user=self.user)

        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["email"])

        profile.full_name = self.cleaned_data["full_name"]
        profile.phone = self.cleaned_data["phone"]

        profile.pungsam_cho = self.cleaned_data["pungsam_cho"]
        profile.pungsam_cho_date = self.cleaned_data["pungsam_cho_date"]

        profile.pungsam_first = self.cleaned_data["pungsam_first"]
        profile.pungsam_first_date = self.cleaned_data["pungsam_first_date"]

        profile.pungsam_gi = self.cleaned_data["pungsam_gi"]
        profile.pungsam_gi_date = self.cleaned_data["pungsam_gi_date"]

        profile.leader_course = self.cleaned_data["leader_course"]
        profile.leader_course_date = self.cleaned_data["leader_course_date"]
        profile.leader_status = self.cleaned_data["leader_status"]

        profile.save(
            update_fields=[
                "full_name",
                "phone",
                "pungsam_cho",
                "pungsam_cho_date",
                "pungsam_first",
                "pungsam_first_date",
                "pungsam_gi",
                "pungsam_gi_date",
                "leader_course",
                "leader_course_date",
                "leader_status",
            ]
        )

        return self.user
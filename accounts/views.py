from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from django.shortcuts import render, redirect
from .forms import SignupForm
from .models import Profile

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

@staff_member_required
def profile_list(request):
    profiles = Profile.objects.select_related("user").order_by("user__username")
    return render(request, "accounts/profile_list.html", {"profiles": profiles})

@staff_member_required
def appoint_chair_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    profile.role = Profile.ROLE_CHAIR
    profile.save(update_fields=["role"])
    return redirect("accounts:profile_list")

@staff_member_required
def demote_chair_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    profile.role = Profile.ROLE_MEMBER
    profile.save(update_fields=["role"])
    return redirect("accounts:profile_list")

def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": form.cleaned_data["full_name"]}
            )
            return redirect("accounts:login")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})

def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("approvals:home")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import SignupForm

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from .models import Profile


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()

            # ✅ Profile 생성(없으면 생성)
            Profile.objects.get_or_create(user=user)

            login(request, user)
            return redirect("approvals:home")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def profile_list(request):
    profiles = Profile.objects.select_related("user").order_by("user__username")
    return render(request, "accounts/profile_list.html", {"profiles": profiles})

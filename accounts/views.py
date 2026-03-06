from django.contrib import messages
from django.contrib.auth import get_user_model, views as auth_views
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from approvals.permissions import CHAIR_GROUP
from .forms import SignupForm, ProfileUpdateForm
from .models import Profile
from .utils import sync_profile_role_from_groups

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("approvals:home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "회원가입이 완료되었습니다. 로그인해주세요.")
            return redirect("accounts:login")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


class CustomLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class CustomLogoutView(auth_views.LogoutView):
    pass


@method_decorator(login_required, name="dispatch")
class CustomPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "비밀번호가 변경되었습니다. 다음 로그인부터 새 비밀번호를 사용하세요.")
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class CustomPasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


def is_staff_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


staff_required = user_passes_test(is_staff_user)


@staff_required
def profile_list(request):
    profiles = Profile.objects.select_related("user").order_by("user__username")
    return render(request, "approvals/profile_list.html", {"profiles": profiles})


@staff_required
@require_POST
def appoint_chair_view(request, profile_id: int):
    profile = get_object_or_404(Profile, id=profile_id)
    user = profile.user

    chair_group, _ = Group.objects.get_or_create(name=CHAIR_GROUP)
    user.groups.add(chair_group)
    sync_profile_role_from_groups(user)

    messages.success(request, f"{profile.display_name()} 님을 위원장으로 임명했습니다.")
    return redirect("accounts:profile_list")


@staff_required
@require_POST
def demote_chair_view(request, profile_id: int):
    profile = get_object_or_404(Profile, id=profile_id)
    user = profile.user

    user.groups.remove(*user.groups.filter(name=CHAIR_GROUP))
    sync_profile_role_from_groups(user)

    messages.success(request, f"{profile.display_name()} 님의 위원장 권한을 해제했습니다.")
    return redirect("accounts:profile_list")


@login_required
def profile_detail(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(
        request,
        "accounts/profile_detail.html",
        {
            "profile_user": request.user,
            "profile": profile,
        },
    )


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "프로필이 수정되었습니다.")
            return redirect("accounts:profile_detail")
    else:
        form = ProfileUpdateForm(user=request.user)

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "form": form,
            "profile_user": request.user,
            "profile": profile,
        },
    )
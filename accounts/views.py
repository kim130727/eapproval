# accounts/views.py
from django.contrib.auth import login, get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy

from approvals.permissions import CHAIR_GROUP  # "CHAIR" 표준값 재사용
from .forms import SignupForm
from .models import Profile

User = get_user_model()

LEGACY_CHAIR_GROUP_NAMES = [
    "chair",
    "위원장",
    "위원장그룹",
    "위원장 그룹",
    "Chair",
    "CHAIR ",  # 공백 실수 대비
    " chair",
]


@staff_member_required
def profile_list(request):
    profiles = Profile.objects.select_related("user").order_by("user__username")
    return render(request, "accounts/profile_list.html", {"profiles": profiles})


def _normalize_chair_groups_for_user(user: User, *, make_chair: bool) -> None:
    """
    ✅ 단일 기준: CHAIR 그룹
    - make_chair=True  => user를 CHAIR 그룹에 포함 + legacy 그룹 제거
    - make_chair=False => user를 CHAIR 그룹에서 제거 + legacy 그룹 제거
    """
    chair_group, _ = Group.objects.get_or_create(name=CHAIR_GROUP)
    legacy_groups = Group.objects.filter(name__in=LEGACY_CHAIR_GROUP_NAMES)

    if make_chair:
        user.groups.add(chair_group)
    else:
        user.groups.remove(chair_group)

    if legacy_groups.exists():
        user.groups.remove(*legacy_groups)


@staff_member_required
def appoint_chair_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)

    # ✅ 그룹이 단일 기준
    _normalize_chair_groups_for_user(profile.user, make_chair=True)

    # role은 signals(m2m_changed)에서 자동 동기화됨
    return redirect("accounts:profile_list")


@staff_member_required
def demote_chair_view(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)

    _normalize_chair_groups_for_user(profile.user, make_chair=False)

    return redirect("accounts:profile_list")


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()

            Profile.objects.update_or_create(
                user=user,
                defaults={"full_name": form.cleaned_data["full_name"]},
            )

            # 신규 유저는 기본 MEMBER(그룹은 건드리지 않음)
            login(request, user)
            return redirect("approvals:home")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
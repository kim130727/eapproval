# accounts/urls.py
from django.urls import path
from .views import signup_view, CustomLoginView, CustomLogoutView
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", signup_view, name="signup"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),

    # ✅ 관리자(스태프)용: 프로필 목록 / 위원장 임명
    path("profiles/", views.profile_list, name="profile_list"),
    path("profiles/<int:profile_id>/appoint-chair/", views.appoint_chair_view, name="appoint_chair"),
    path("profiles/<int:profile_id>/demote-chair/", views.demote_chair_view, name="demote_chair"),
]

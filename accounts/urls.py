from django.urls import path
from .views import (
    signup_view,
    CustomLoginView,
    CustomLogoutView,
    CustomPasswordChangeView,
    CustomPasswordChangeDoneView,
    profile_list,
    appoint_chair_view,
    demote_chair_view,
    profile_detail,
    profile_edit,
)

app_name = "accounts"

urlpatterns = [
    path("signup/", signup_view, name="signup"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),

    path("password/change/", CustomPasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", CustomPasswordChangeDoneView.as_view(), name="password_change_done"),

    path("profile/", profile_detail, name="profile_detail"),
    path("profile/edit/", profile_edit, name="profile_edit"),  # 프로필 수정

    path("profiles/", profile_list, name="profile_list"),
    path("profiles/<int:profile_id>/appoint-chair/", appoint_chair_view, name="appoint_chair"),
    path("profiles/<int:profile_id>/demote-chair/", demote_chair_view, name="demote_chair"),
]
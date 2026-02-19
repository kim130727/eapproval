from django.urls import path
from .views import signup_view, CustomLoginView, CustomLogoutView
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", signup_view, name="signup"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("admin/appoint-chair/<int:user_id>/", views.appoint_chair_view, name="appoint_chair"),
    path("profiles/<int:profile_id>/demote-chair/", views.demote_chair_view, name="demote_chair"),
]

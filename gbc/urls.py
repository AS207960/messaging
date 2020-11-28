from django.urls import path
from . import views

app_name = "gbc"
urlpatterns = [
    path("oauth/auth/", views.oauth_auth),
    path("bm_webhook/", views.bm_webhook)
]

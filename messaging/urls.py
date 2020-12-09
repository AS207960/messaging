from django.urls import path
from . import views

app_name = "messaging"
urlpatterns = [
    path("oauth/redirect/", views.oauth_redirect, name='messaging_oauth_redirect'),
]

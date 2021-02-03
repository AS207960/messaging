from django.urls import path
from . import views

app_name = "rcs"
urlpatterns = [
    path("rcs_webhook/", views.rcs_webhook),
]

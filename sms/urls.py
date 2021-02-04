from django.urls import path
from . import views

app_name = "sms"
urlpatterns = [
    path("vsms_webhook/", views.vsms_postback_webhook),
    path("twilio_webhook/", views.twilio_webhook),
    path("twilio_status_webhook/", views.twilio_status_webhook, name='twilio_status_webhook'),
]

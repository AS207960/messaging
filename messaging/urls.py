from django.urls import path
from . import views

app_name = "messaging"
urlpatterns = [
    path("brand_oauth/redirect/", views.oauth_redirect, name='messaging_oauth_redirect'),
    path("calendar_event/<str:event_data>", views.calendar_event, name='calendar_event')
]

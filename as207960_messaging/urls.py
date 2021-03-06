"""as207960_messaging URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('gbc/', include('gbc.urls')),
    path('rcs/', include('rcs.urls')),
    path('sms/', include('sms.urls')),
    path('auth/', include('django_keycloak_auth.urls')),
    path('api/', include('messaging.api.urls')),
    path('', include('messaging.urls')),
]

if settings.DEBUG:
    urlpatterns += static("static/", document_root=settings.STATIC_ROOT)
    urlpatterns += static("media/", document_root=settings.MEDIA_ROOT)

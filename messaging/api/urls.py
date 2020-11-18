from django.urls import include, path
from rest_framework import routers, schemas
import rest_framework_nested.routers
from . import views

router = routers.DefaultRouter()
router.register(r'brands', views.BrandViewSet, basename='brand')

brand_router = rest_framework_nested.routers.NestedDefaultRouter(router, r'brands', lookup='brand')
brand_router.register(r'messages', views.MessageViewSet, basename='brand-messages')
brand_router.register(r'representatives', views.RepresentativeSet, basename='brand-representatives')


urlpatterns = [
    path('', include(router.urls)),
    path('', include(brand_router.urls)),
    path('openapi', schemas.get_schema_view(
        title="AS207960 Messaging",
        version="0.0.1"
    ), name='openapi-schema'),
]
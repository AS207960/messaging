from rest_framework import permissions
from as207960_utils.api import auth


def brand_keycloak(db_class, pre_filtered=False):
    class BrandKeycloak(permissions.BasePermission):
        def has_permission(self, request, view):
            if not isinstance(request.auth, auth.OAuthToken):
                return False

            if request.method == "POST":
                return db_class.objects.get(id=view.kwargs["brand_pk"]).has_scope(request.auth.token, 'edit')
            else:
                return True

        def has_object_permission(self, request, view, obj):
            if pre_filtered:
                return True
            elif request.method in ("GET", "HEAD"):
                return obj.brand.has_scope(request.auth.token, 'view')
            elif request.method in ("PUT", "PATCH", "DELETE"):
                return obj.brand.has_scope(request.auth.token, 'edit')

    return BrandKeycloak

from rest_framework import viewsets, mixins
from django.core.exceptions import PermissionDenied
from as207960_utils.api import auth
import as207960_utils.api.permissions
from django.utils import timezone
from . import serializers, permissions
from .. import models, tasks


class BrandViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = serializers.BrandSerializer
    queryset = models.Brand.objects.all()
    permission_classes = [as207960_utils.api.permissions.keycloak(models.Brand)]

    def filter_queryset(self, queryset):
        if not isinstance(self.request.auth, auth.OAuthToken):
            raise PermissionDenied

        return models.Brand.get_object_list(self.request.auth.token)


class MessageViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = serializers.MessageSerializer
    queryset = models.Message.objects.all()
    permission_classes = [permissions.brand_keycloak(models.Brand)]

    def filter_queryset(self, queryset):
        if not isinstance(self.request.auth, auth.OAuthToken):
            raise PermissionDenied

        return models.Message.objects.filter(brand=self.kwargs['brand_pk'])

    def perform_create(self, serializer: serializers.MessageSerializer):
        serializer.save(
            timestamp=timezone.now(),
            brand_id=self.kwargs['brand_pk'],
            direction=models.Message.DIRECTION_OUTGOING
        )
        tasks.process_message.delay(serializer.instance.id)


class RepresentativeSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = serializers.RepresentativeSerializer
    queryset = models.Representative.objects.all()
    permission_classes = [permissions.brand_keycloak(models.Brand)]

    def filter_queryset(self, queryset):
        if not isinstance(self.request.auth, auth.OAuthToken):
            raise PermissionDenied

        return models.Representative.objects.filter(brand=self.kwargs['brand_pk'])

    def perform_create(self, serializer: serializers.RepresentativeSerializer):
        serializer.save(
            brand_id=self.kwargs['brand_pk'],
            force_insert=False
        )

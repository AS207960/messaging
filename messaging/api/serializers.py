from rest_framework import serializers
from .. import models
import rest_framework_nested.relations
import collections


class WriteOnceMixin:
    def get_fields(self):
        fields = super().get_fields()

        if 'update' in getattr(self.context.get('view'), 'action', ''):
            self._set_write_once_fields(fields)
            self._set_write_after_fields(fields)

        return fields

    def _set_write_once_fields(self, fields):
        write_once_fields = getattr(self.Meta, 'write_once_fields', None)
        if not write_once_fields:
            return

        if not isinstance(write_once_fields, (list, tuple)):
            raise TypeError(
                'The `write_once_fields` option must be a list or tuple. '
                'Got {}.'.format(type(write_once_fields).__name__)
            )

        for field_name in write_once_fields:
            fields[field_name].read_only = True

    def _set_write_after_fields(self, fields):
        write_after_fields = getattr(self.Meta, 'write_after_fields', None)
        if not write_after_fields:
            return

        if not isinstance(write_after_fields, (list, tuple)):
            raise TypeError(
                'The `write_after_fields` option must be a list or tuple. '
                'Got {}.'.format(type(write_after_fields).__name__)
            )

        for field_name in write_after_fields:
            fields[field_name].read_only = False


class BrandPermissionPrimaryKeyRelatedFieldValidator:
    requires_context = True

    def __call__(self, value, ctx):
        if (not value.brand.has_scope(ctx.auth_token, 'view') or value.brand_id != ctx.brand) or not ctx.auth_token:
                raise serializers.ValidationError("you don't have permission to reference this object")


class BrandPermissionPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, model, **kwargs):
        self.model = model
        self.auth_token = None
        self.brand = None
        super().__init__(queryset=model.objects.all(), **kwargs)

    def get_choices(self, cutoff=None):
        queryset = self.get_queryset().filter(brand_id=self.brand)

        if queryset is None:
            return {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        return collections.OrderedDict([
            (
                self.to_representation(item),
                self.display_value(item)
            )
            for item in queryset
        ])

    def get_validators(self):
        validators = super().get_validators()
        validators.append(BrandPermissionPrimaryKeyRelatedFieldValidator())
        return validators


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Brand
        fields = ('url', 'id', 'name', 'webhook_url', 'messages', 'representatives')
        read_only_fields = ('id', 'name',)

    messages = serializers.HyperlinkedIdentityField(
        view_name='brand-messages-list',
        lookup_url_kwarg='brand_pk',
        lookup_field='id'
    )
    representatives = serializers.HyperlinkedIdentityField(
        view_name='brand-representatives-list',
        lookup_url_kwarg='brand_pk',
        lookup_field='id'
    )


class MessageSerializer(serializers.ModelSerializer, WriteOnceMixin):
    class Meta:
        model = models.Message
        fields = ('url', 'id', 'direction', 'state', 'platform', 'platform_conversation_id', 'client_message_id',
                  'timestamp', 'metadata', 'media_type', 'content', 'error_description', 'brand_url', 'brand',
                  'representative', 'representative_url')
        read_only_fields = ('id', 'direction', 'state', 'timestamp', 'metadata',  'error_description', 'brand')
        write_once_fields = ('platform', 'platform_conversation_id', 'client_message_id', 'media_type', 'content')

    url = rest_framework_nested.relations.NestedHyperlinkedIdentityField(
        view_name='brand-messages-detail',
        parent_lookup_kwargs={'brand_pk': 'brand__pk'},
        lookup_field="id",
        lookup_url_kwarg="pk"
    )
    brand_url = serializers.HyperlinkedRelatedField(
        lookup_field='brand_id',
        lookup_url_kwarg='pk',
        view_name='brand-detail',
        read_only=True
    )
    representative_url = rest_framework_nested.relations.NestedHyperlinkedRelatedField(
        lookup_field='representative_id',
        lookup_url_kwarg='pk',
        parent_lookup_kwargs={'brand_pk': 'brand__pk'},
        view_name='brand-representatives-detail',
        read_only=True,
        allow_null=True
    )
    representative = BrandPermissionPrimaryKeyRelatedField(model=models.Representative, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["representative"].brand = self.context['view'].kwargs['brand_pk']
        if 'request' in self.context:
            self.fields["representative"].auth_token = self.context['request'].auth.token

    def to_representation(self, instance: models.Message):
        ret = {
            "url": self.fields["url"].to_representation(instance),
            "id": self.fields["id"].to_representation(instance),
            "platform": instance.platform,
            "platform_conversation_id": instance.platform_conversation_id,
            "client_message_id": instance.client_message_id,
            "timestamp": self.fields["timestamp"].to_representation(instance.timestamp),
            "metadata": instance.metadata,
            "media_type": instance.media_type,
            "content": instance.content,
            "error_description": instance.error_description,
            "brand_url": self.fields["brand_url"].to_representation(instance),
            "brand": self.fields["brand"].to_representation(instance),
            "representative_url": self.fields["representative_url"].to_representation(instance.representative)
            if instance.representative else None,
            "representative": self.fields["representative"].to_representation(instance.representative)
            if instance.representative else None,
        }

        if instance.direction == models.Message.DIRECTION_INCOMING:
            ret["direction"] = "incoming"
        elif instance.direction == models.Message.DIRECTION_OUTGOING:
            ret["direction"] = "outgoing"
        else:
            ret["state"] = "unknown"

        if instance.state == models.Message.STATE_ACCEPTED:
            ret["state"] = "accepted"
        elif instance.state == models.Message.STATE_DISPATCHED:
            ret["state"] = "dispatched"
        elif instance.state == models.Message.STATE_DELIVERED:
            ret["state"] = "delivered"
        elif instance.state == models.Message.STATE_READ:
            ret["state"] = "read"
        elif instance.state == models.Message.STATE_FAILED:
            ret["state"] = "failed"
        else:
            ret["state"] = "unknown"

        return ret


class RepresentativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Representative
        fields = ('url', 'id', 'brand_url', 'brand', 'name', 'is_bot', 'avatar')
        read_only_fields = ('id', 'brand')

    url = rest_framework_nested.relations.NestedHyperlinkedIdentityField(
        view_name='brand-representatives-detail',
        parent_lookup_kwargs={'brand_pk': 'brand__pk'},
        lookup_field="id",
        lookup_url_kwarg="pk"
    )
    brand_url = serializers.HyperlinkedRelatedField(
        lookup_field='brand_id',
        lookup_url_kwarg='pk',
        view_name='brand-detail',
        read_only=True
    )

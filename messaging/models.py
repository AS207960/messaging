from django.db import models
import as207960_utils.models
import django_keycloak_auth.clients
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image
import io
import uuid


class Brand(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_brand", primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    webhook_url = models.URLField()
    webhook_signing_secret = models.CharField(max_length=255, default=uuid.uuid4)
    resource_id = models.UUIDField(null=True, db_index=True)
    authorization_url = models.URLField(blank=True, null=True)
    client_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_object_list(cls, access_token: str, action='view'):
        return cls.objects.filter(
            resource_id__in=as207960_utils.models.get_object_ids(access_token, 'brand', action))

    @classmethod
    def has_class_scope(cls, access_token: str, action='view'):
        scope_name = f"{action}-brand"
        return django_keycloak_auth.clients.get_authz_client() \
            .eval_permission(access_token, f"brand", scope_name)

    def has_scope(self, access_token: str, action='view'):
        scope_name = f"{action}-brand"
        return as207960_utils.models.eval_permission(access_token, self.resource_id, scope_name)

    def save(self, *args, **kwargs):
        as207960_utils.models.sync_resource_to_keycloak(
            self,
            display_name="Brand", scopes=[
                'view-brand',
                'edit-brand',
                'delete-brand',
            ],
            urn="urn:as207960:messaging:brand", super_save=super().save, view_name=None,
            args=args, kwargs=kwargs
        )

    def delete(self, *args, **kwargs):
        super().delete(*args, *kwargs)
        as207960_utils.models.delete_resource(self.resource_id)


class Representative(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_representative", primary_key=True, editable=False)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    is_bot = models.BooleanField(blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    avatar = models.ImageField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if bool(self.avatar) and self.avatar.file is not None and isinstance(self.avatar.file, UploadedFile):
            img = Image.open(io.BytesIO(self.avatar.read()))
            img.thumbnail((256, 256 * self.avatar.height / self.avatar.width), Image.ANTIALIAS)
            output = io.BytesIO()
            if img.mode == 'RGBA':
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, img.split()[-1])
                img = background
            img.save(output, format='JPEG', quality=50, optimise=True)
            self.avatar.save("%s.jpg" % self.avatar.name.split('.')[0], ContentFile(output.getvalue()), save=False)
        super().save(*args, **kwargs)


class Message(models.Model):
    PLATFORM_GBM = "google-business-messaging"
    PLATFORMS = (
        (PLATFORM_GBM, "Google Business Messaging"),
    )

    DIRECTION_INCOMING = "I"
    DIRECTION_OUTGOING = "O"
    DIRECTIONS = (
        (DIRECTION_INCOMING, "Incoming"),
        (DIRECTION_OUTGOING, "Outgoing")
    )

    STATE_ACCEPTED = "A"
    STATE_DISPATCHED = "E"
    STATE_DELIVERED = "D"
    STATE_READ = 'R'
    STATE_FAILED = "F"
    STATES = (
        (STATE_ACCEPTED, "Accepted"),
        (STATE_DISPATCHED, "Dispatched"),
        (STATE_DELIVERED, "Delivered"),
        (STATE_READ, "Read"),
        (STATE_FAILED, "Failed"),
    )

    id = as207960_utils.models.TypedUUIDField("messaging_message", primary_key=True, editable=False)
    direction = models.CharField(max_length=1, choices=DIRECTIONS)
    state = models.CharField(max_length=1, choices=STATES, default=STATE_ACCEPTED)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    representative = models.ForeignKey(Representative, on_delete=models.SET_NULL, blank=True, null=True)
    platform = models.CharField(max_length=255, choices=PLATFORMS)
    platform_conversation_id = models.CharField(max_length=255, db_index=True)
    platform_message_id = models.CharField(max_length=255, db_index=True, blank=True, null=True)
    platform_dedup_id = models.CharField(max_length=255, db_index=True)
    client_message_id = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField()
    metadata = models.JSONField(default=dict)
    media_type = models.CharField(max_length=255)
    content = models.JSONField(blank=True, null=True)
    error_description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

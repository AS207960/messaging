from django.db import models
import messaging.models
import as207960_utils.models


class Brand(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_gbcbrand", primary_key=True)
    brand = models.OneToOneField(messaging.models.Brand, on_delete=models.CASCADE)
    google_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.brand.name


class BusinessMessagingAgent(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_gbmagent", primary_key=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    google_id = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    logo = models.ImageField()

    def __str__(self):
        return f"({self.brand.brand.name}) {self.name}"


class OAuthState(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_gbcauthstate", primary_key=True)
    google_state = models.TextField()
    redirect_uri = models.URLField()
    auth_code = models.TextField(blank=True, null=True)

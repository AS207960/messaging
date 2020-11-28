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


# class OAuthState(models.Model):
#     id = models.UUIDField(unique=True, primary_key=True, default=uuid.uuid4)
#     conversation = models.ForeignKey(
#         ConversationPlatform,
#         on_delete=models.CASCADE,
#         related_name="apple_business_chat_account_linking_state",
#     )
#     timestamp = models.DateTimeField(auto_now_add=True)

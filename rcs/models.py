from django.db import models
import as207960_utils.models
import phonenumber_field.modelfields
import messaging.models


class Agent(models.Model):
    REGION_ASIA = "asia"
    REGION_EUROPE = "europe"
    REGION_US = "us"
    REGIONS = (
        (REGION_ASIA, "Asia"),
        (REGION_EUROPE, "Europe"),
        (REGION_US, "US"),
    )

    id = as207960_utils.models.TypedUUIDField("messaging_rcsagent", primary_key=True)
    brand = models.OneToOneField(messaging.models.Brand, on_delete=models.CASCADE, related_name='rcs_agent')
    service_account_key = models.TextField()
    subscription_name = models.CharField(max_length=255)
    pull_subscription = models.BooleanField(default=False, blank=True)
    region = models.CharField(max_length=64, default=REGION_EUROPE)

    def __str__(self):
        return self.brand.name


class MSISDN(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_rcsmsisdn", primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    msisdn = phonenumber_field.modelfields.PhoneNumberField()
    supports_rcs = models.BooleanField(default=False, blank=True)
    supports_revocation = models.BooleanField(default=False, blank=True)
    supports_rich_card_standalone = models.BooleanField(default=False, blank=True)
    supports_rich_card_carousel = models.BooleanField(default=False, blank=True)
    supports_action_calendar = models.BooleanField(default=False, blank=True)
    supports_action_dial = models.BooleanField(default=False, blank=True)
    supports_action_url = models.BooleanField(default=False, blank=True)
    supports_action_share_location = models.BooleanField(default=False, blank=True)
    supports_action_view_location = models.BooleanField(default=False, blank=True)
    supports_payments_v1 = models.BooleanField(default=False, blank=True)

    class Meta:
        verbose_name = "MSISDN"
        verbose_name_plural = "MSISDNs"

    def __str__(self):
        return self.msisdn.as_e164
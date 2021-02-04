from django.db import models
import as207960_utils.models
import messaging.models
import phonenumber_field.modelfields


class TwilioAccount(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_twilioaccount", primary_key=True)
    account_sid = models.CharField(max_length=255)
    account_token = models.CharField(max_length=255)

    def __str__(self):
        return self.account_sid


class Agent(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_smsagent", primary_key=True)
    msisdn = phonenumber_field.modelfields.PhoneNumberField()
    brand = models.OneToOneField(messaging.models.Brand, on_delete=models.CASCADE, related_name='sms_agent')
    twilio_account = models.ForeignKey(TwilioAccount, on_delete=models.CASCADE, related_name='sms_agents')
    vsms_agent_id = models.CharField(max_length=255, blank=True, null=True)
    vsms_private_key = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.brand.name


class MSISDN(models.Model):
    id = as207960_utils.models.TypedUUIDField("messaging_vsmskey", primary_key=True)
    msisdn = phonenumber_field.modelfields.PhoneNumberField()
    vsms_public_key = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "MSISDN"
        verbose_name_plural = "MSISDNs"

    def __str__(self):
        return self.msisdn.as_e164

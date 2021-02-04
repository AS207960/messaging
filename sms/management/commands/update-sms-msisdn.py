from django.core.management.base import BaseCommand
import sms.models
import sms.tasks


class Command(BaseCommand):
    def handle(self, *args, **options):
        msisdns = list(sms.models.MSISDN.objects.all())
        r = sms.tasks.session.post(
            "https://verifiedsms.googleapis.com/v1/enabledUserKeys:batchGet",
            json={
                "phoneNumbers": list(map(lambda m: m.msisdn.as_e164, msisdns))
            }
        )
        r.raise_for_status()
        data = r.json()

        for msisdn in msisdns:
            vsms_data = next(filter(lambda u: u["phoneNumber"] == msisdn.msisdn.as_e164, data["userKeys"]), None) \
                if "userKeys" in data else None
            if vsms_data:
                print(msisdn.vsms_public_key, vsms_data)
                msisdn.vsms_public_key = vsms_data["publicKey"]
            else:
                msisdn.vsms_public_key = None
            msisdn.save()

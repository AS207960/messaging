from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime
import rcs.models
import messaging.models
import rcs.tasks
import sms.tasks
import google.oauth2.service_account
import google.auth.transport.requests
import json


class Command(BaseCommand):
    def handle(self, *args, **options):
        message_expiry = timezone.now() - datetime.timedelta(hours=1)
        for agent_obj in rcs.models.Agent.objects.all():
            base_url = f"https://{agent_obj.region}-rcsbusinessmessaging.googleapis.com"

            credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                json.loads(agent_obj.service_account_key),
                scopes=rcs.tasks.SCOPES
            )
            session = google.auth.transport.requests.AuthorizedSession(credentials)

            for message in agent_obj.brand.message_set.filter(
                state=messaging.models.Message.STATE_DISPATCHED,
                platform=messaging.models.Message.PLATFORM_MSISDN,
                timestamp__lt=message_expiry,
            ):
                if message.metadata.get("msisdn.transport") == "rcs":
                    session.delete(
                        f"{base_url}/v1/phones/{message.platform_conversation_id}/agentMessages/{message.id}"
                    )
                    sms.tasks.send_message.delay(message.id)

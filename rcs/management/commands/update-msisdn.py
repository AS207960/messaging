from django.core.management.base import BaseCommand
import rcs.models
import rcs.tasks
import google.oauth2.service_account
import google.auth.transport.requests
import json
import uuid


class Command(BaseCommand):
    def handle(self, *args, **options):
        for agent_obj in rcs.models.Agent.objects.all():
            base_url = f"https://{agent_obj.region}-rcsbusinessmessaging.googleapis.com"

            credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                json.loads(agent_obj.service_account_key),
                scopes=rcs.tasks.SCOPES
            )
            session = google.auth.transport.requests.AuthorizedSession(credentials)

            for msisdn in agent_obj.msisdn_set.all():
                session.post(
                    f"{base_url}/v1/phones/{msisdn.msisdn.as_e164}/capability:requestCapabilityCallback",
                    json={
                        "requestId": str(uuid.uuid4())
                    }
                )

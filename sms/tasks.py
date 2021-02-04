from celery import shared_task
from django.conf import settings
from django.shortcuts import reverse
import messaging.models
import messaging.tasks
import phonenumbers
import twilio.rest
import twilio.base.exceptions
import urllib.parse
import google.oauth2.service_account
import google.auth.transport.requests
import base64
import cryptography.hazmat.primitives.asymmetric.ec
import cryptography.hazmat.primitives.kdf.hkdf
import cryptography.hazmat.primitives.hashes
import cryptography.hazmat.primitives.serialization
from . import models

VSMS_RATE_LIMIT_SALT = \
    "xELpwbCabRriJEkOYBagfJpHrrmNqlaZMTxsacBQjsLjUHtQexWNQCiMCkrxBzWEifExJkkOJwOziTQQJyRWVUbauuCHZrYlenSAiqtKtT"

credentials = google.oauth2.service_account.Credentials.from_service_account_file(
    settings.VSMS_SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/verifiedsms"]
)
session = google.auth.transport.requests.AuthorizedSession(credentials)


def get_vsms_key(msisdn):
    msisdn_obj = models.MSISDN.objects.filter(msisdn=msisdn).first()
    if not msisdn_obj:
        r = session.post(
            "https://verifiedsms.googleapis.com/v1/enabledUserKeys:batchGet",
            json={
                "phoneNumbers": [msisdn]
            }
        )
        r.raise_for_status()
        data = r.json()
        if "userKeys" in data and len(data["userKeys"]):
            msisdn_obj = models.MSISDN(
                msisdn=data["userKeys"][0]["phoneNumber"], vsms_public_key=data["userKeys"][0]["publicKey"]
            )
        else:
            msisdn_obj = models.MSISDN(
                msisdn=msisdn, vsms_public_key=None
            )
        msisdn_obj.save()
    return msisdn_obj.vsms_public_key


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3,
    ignore_result=True
)
def send_message(message_id):
    message = messaging.models.Message.objects.get(id=message_id)

    try:
        number = phonenumbers.parse(message.platform_conversation_id)
    except phonenumbers.phonenumberutil.NumberParseException:
        message.state = message.STATE_FAILED
        message.error_description = "Invalid MSISDN"
        message.save()
        messaging.tasks.send_message.delay(message.id)
        return
    e164_number = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)

    try:
        agent_obj = message.brand.sms_agent
    except message.brand.DoesNotExist:
        message.state = message.STATE_FAILED
        message.error_description = "Brand does not support SMS"
        message.save()
        messaging.tasks.send_message.delay(message.id)
        return

    vsms_public_key = get_vsms_key(e164_number)
    vsms_shared_key = None

    if vsms_public_key:
        message.metadata["msisdn.vmsm"] = "user_enabled"
    else:
        message.metadata["msisdn.vmsm"] = "user_disabled"
    message.metadata["msisdn.transport"] = "sms"
    message.save()
    messaging.tasks.send_message.delay(message.id)

    if agent_obj.vsms_private_key and vsms_public_key:
        vsms_private_key = cryptography.hazmat.primitives.serialization.load_pem_private_key(
            str(agent_obj.vsms_private_key).encode(), password=None
        )
        vsms_public_key = cryptography.hazmat.primitives.serialization.load_der_public_key(
            base64.b64decode(vsms_public_key.encode())
        )
        vsms_shared_key = vsms_private_key.exchange(
            cryptography.hazmat.primitives.asymmetric.ec.ECDH(),
            vsms_public_key
        )

    twilio_client = twilio.rest.Client(agent_obj.twilio_account.account_sid, agent_obj.twilio_account.account_token)

    msg_body = None
    msg_other = {}

    if message.media_type == "chat_state":
        return
    else:
        if message.media_type == "text":
            msg_body = message.content
        elif message.media_type == "file":
            if not ("url" in message.content):
                message.state = message.STATE_FAILED
                message.error_description = "Invalid message"
                message.save()
                messaging.tasks.send_message.delay(message.id)
                return

            msg_body = ""
            msg_other["media_url"] = message.content["url"]
        elif message.media_type == "select":
            if not ("media_type" in message.content and "options" in message.content and "content" in message.content):
                message.state = message.STATE_FAILED
                message.error_description = "Invalid message"
                message.save()
                messaging.tasks.send_message.delay(message.id)
                return

            if message.content["media_type"] == "text":
                msg_body = f'{message.content["content"]}\n'
            elif message.content["media_type"] == "file":
                if not ("url" in message.content["content"]):
                    message.state = message.STATE_FAILED
                    message.error_description = "Invalid message"
                    message.save()
                    messaging.tasks.send_message.delay(message.id)
                    return

                msg_body = ""
                msg_other["media_url"] = message.content["content"]["url"]

            for option in message.content["options"]:
                if not ("media_type" in option and "content" in option):
                    message.state = message.STATE_FAILED
                    message.error_description = "Invalid message"
                    message.save()
                    messaging.tasks.send_message.delay(message.id)
                    return

                if option["media_type"] == "text":
                    pass
                elif option["media_type"] == "url":
                    content = option["content"]
                    if not ("url" in content and "text" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        messaging.tasks.send_message.delay(message.id)
                        return

                    fallback_url = messaging.tasks.shorten_link(
                        agent_obj.brand, content["url"]
                    )

                    msg_body += f'\n{content["text"]}: {fallback_url}'
                elif option["media_type"] == "dial":
                    content = option["content"]
                    if not ("number" in content and "text" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        messaging.tasks.send_message.delay(message.id)
                        return

                    msg_body += f'\n{content["text"]}: {content["number"]}'
                elif option["media_type"] == "location":
                    content = option["content"]
                    if not ("lat_long" in content or "query" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        messaging.tasks.send_message.delay(message.id)
                        return

                    if "query" in content:
                        query = urllib.parse.quote_plus(content["query"])
                        fallback_url = f"https://www.google.com/maps/search/?api=1&query={query}"
                    else:
                        lat_long = content['lat_long']
                        fallback_url = f"https://www.google.com/maps/search/?api=1&" \
                                       f"query={lat_long['latitude']},{lat_long['longitude']}"

                    msg_body += f'\n{content["text"]}: {fallback_url}'
                elif option["media_type"] == "share_location":
                    pass
                elif option["media_type"] == "calendar_event":
                    content = option["content"]
                    if not (
                            "start_time" in content and "end_time" in content and
                            "title" in content and "description" in content
                    ):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        messaging.tasks.send_message.delay(message.id)
                        return

                    fallback_url = messaging.tasks.make_calendar_fallback(message, content)
                    fallback_url = messaging.tasks.shorten_link(
                        agent_obj.brand, fallback_url,
                        title=content["title"],
                        description=content["description"]
                    )

                    msg_body += f'\n{content["text"]}: {fallback_url}'
                # elif option["media_type"] == "login":
                #     suggestion = {
                #         "authenticationRequest": {
                #             "oauth": {
                #                 "clientId": message.brand.brand.id,
                #                 "codeChallenge": secrets.token_urlsafe(32),
                #                 "scopes": ["as207960-messaging-oauth"],
                #             }
                #         }
                #     }
                else:
                    message.state = message.STATE_FAILED
                    message.error_description = "Invalid message"
                    message.save()
                    messaging.tasks.send_message.delay(message.id)
                    return

        else:
            message.state = message.STATE_FAILED
            message.error_description = "Invalid message"
            message.save()
            messaging.tasks.send_message.delay(message.id)
            return

    if msg_body is not None:
        if vsms_shared_key:
            vsms_hash = base64.urlsafe_b64encode(cryptography.hazmat.primitives.kdf.hkdf.HKDF(
                algorithm=cryptography.hazmat.primitives.hashes.SHA256(),
                length=32,
                salt=None,
                info=msg_body.encode('utf-8'),
            ).derive(vsms_shared_key)).decode()
            vsms_rate_limit_token = base64.urlsafe_b64encode(cryptography.hazmat.primitives.kdf.hkdf.HKDF(
                algorithm=cryptography.hazmat.primitives.hashes.SHA256(),
                length=32,
                salt=None,
                info=VSMS_RATE_LIMIT_SALT.encode('utf-8'),
            ).derive(vsms_shared_key)).decode()
            vsms_postback = base64.urlsafe_b64encode(str(message.id).encode()).decode()

            r = session.post(
                "https://verifiedsms.googleapis.com/v1/messages:batchCreate",
                json={
                    "messages": [{
                        "agentId": agent_obj.vsms_agent_id,
                        "hash": vsms_hash,
                        "rateLimitToken": vsms_rate_limit_token,
                        "postbackData": vsms_postback,
                    }]
                }
            )
            r.raise_for_status()

        try:
            msg_resp = twilio_client.messages.create(
                to=e164_number,
                provide_feedback=True,
                from_=agent_obj.msisdn.as_e164,
                body=msg_body,
                status_callback=settings.EXTERNAL_URL_BASE + reverse('sms:twilio_status_webhook'),
                **msg_other
            )
        except twilio.base.exceptions.TwilioException:
            message.state = message.STATE_FAILED
            message.error_description = "Message sending failed"
            message.save()
            message.save()
            messaging.tasks.send_message.delay(message.id)
            return

        message.platform_message_id = msg_resp.sid
        message.state = message.STATE_DISPATCHED
        message.save()
        messaging.tasks.send_message.delay(message.id)

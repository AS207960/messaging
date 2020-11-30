from celery import shared_task
import messaging.models
import google.oauth2.service_account
import google.auth.transport.requests
from django.conf import settings
import secrets

credentials = google.oauth2.service_account.Credentials.from_service_account_file(
    settings.GBM_SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/businessmessages"]
)
session = google.auth.transport.requests.AuthorizedSession(credentials)


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3,
    ignore_result=True
)
def send_message(message_id):
    message = messaging.models.Message.objects.get(id=message_id)

    related_messages = messaging.models.Message.objects.filter(
        direction=messaging.models.Message.DIRECTION_INCOMING,
        platform_conversation_id=message.platform_conversation_id,
    ).count()

    if related_messages == 0:
        message.state = message.STATE_FAILED
        message.error_description = "Not a valid conversation"
        message.save()
        return

    representative = {}
    if not message.representative:
        representative["representativeType"] = "BOT"
    else:
        representative["representativeType"] = "BOT" if message.representative.is_bot else "HUMAN"
        representative["displayName"] = message.representative.name
        representative["avatarImage"] = message.representative.avatar.url if message.representative.avatar else None

    body = {
        "representative": representative
    }

    if message.media_type == "chat_state":
        url = f"https://businessmessages.googleapis.com/v1/conversations/{message.platform_conversation_id}/events" \
              f"?eventId={message.id}"
        if "state" not in message.content:
            return
        if message.content["state"] == "composing":
            body["eventType"] = "TYPING_STARTED"
        elif message.content["state"] == "paused":
            body["eventType"] = "TYPING_STOPPED"
        elif message.content["state"] == "representative_joined":
            body["eventType"] = "REPRESENTATIVE_JOINED"
        elif message.content["state"] == "representative_left":
            body["eventType"] = "REPRESENTATIVE_LEFT"
        else:
            message.state = message.STATE_FAILED
            message.error_description = "Invalid message"
            return
    else:
        url = f"https://businessmessages.googleapis.com/v1/conversations/{message.platform_conversation_id}/messages"
        body["messageId"] = message.id
        if message.media_type == "text":
            body["text"] = message.content
        elif message.media_type == "gbm.card":
            body["richCard"] = message.content
        elif message.media_type == "select":
            if not ("media_type" in message.content and "options" in message.content and "content" in message.content):
                message.state = message.STATE_FAILED
                message.error_description = "Invalid message"
                message.save()
                return

            if message.content["media_type"] == "text":
                body["text"] = message.content["content"]
            elif message.content["media_type"] == "gbm.card":
                body["richCard"] = message.content["content"]

            body["suggestions"] = []
            for option in message.content["options"]:
                if not ("media_type" in option, "content" in option):
                    message.state = message.STATE_FAILED
                    message.error_description = "Invalid message"
                    message.save()
                    return

                if option["media_type"] == "text":
                    suggestion = {
                        "reply": {
                            "text": option["content"],
                            "postbackData": option.get("postback", option["content"])
                        }
                    }
                elif option["media_type"] == "url":
                    content = option["content"]
                    if not ("url" in content and "text" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        return
                    suggestion = {
                        "action": {
                            "text": content["text"],
                            "postbackData": option.get("postback", content["text"]),
                            "openUrlAction": {
                                "url": content["url"]
                            }
                        }
                    }
                elif option["media_type"] == "dial":
                    content = option["content"]
                    if not ("number" in content and "text" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        return
                    suggestion = {
                        "action": {
                            "text": content["text"],
                            "postbackData": option.get("postback", content["text"]),
                            "dialAction": {
                                "phoneNumber": content["number"]
                            }
                        }
                    }
                elif option["media_type"] == "login":
                    suggestion = {
                        "authenticationRequest": {
                            "oauth": {
                                "clientId": message.brand.brand.id,
                                "codeChallenge": secrets.token_urlsafe(32),
                                "scopes": [],
                            }
                        }
                    }
                else:
                    message.state = message.STATE_FAILED
                    message.error_description = "Invalid message"
                    message.save()
                    return

                body["suggestions"].append(suggestion)
        else:
            message.state = message.STATE_FAILED
            message.error_description = "Invalid message"
            message.save()
            return

    if url and body:
        r = session.post(url, json=body)
        if r.status_code != 200:
            message.state = message.STATE_FAILED
            message.error_description = r.json()["error"]["message"]
        else:
            message.state = message.STATE_DISPATCHED
            message.platform_message_id = r.json()["name"]
        message.save()

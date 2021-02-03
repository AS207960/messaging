from celery import shared_task
import messaging.models
import messaging.tasks
import google.oauth2.service_account
import google.auth.transport.requests
from django.conf import settings
import urllib.parse
import json
import dateutil.parser
import datetime
import phonenumbers
from . import models

SCOPES = ["https://www.googleapis.com/auth/rcsbusinessmessaging"]


def map_file(message, content):
    if not ("url" in content):
        message.state = message.STATE_FAILED
        message.error_description = "Invalid message"
        message.save()
        return

    return {
        "fileUrl": content["url"],
        "forceRefresh": content.get("force_new", False)
    }


def update_msisdn_features(features, msisdn: models.MSISDN):
    msisdn.supports_revocation = "REVOCATION" in features
    msisdn.supports_rich_card_standalone = "RICHCARD_STANDALONE" in features
    msisdn.supports_rich_card_carousel = "RICHCARD_CAROUSEL" in features
    msisdn.supports_action_calendar = "ACTION_CREATE_CALENDAR_EVENT" in features
    msisdn.supports_action_dial = "ACTION_DIAL" in features
    msisdn.supports_action_url = "ACTION_OPEN_URL" in features
    msisdn.supports_action_share_location = "ACTION_SHARE_LOCATION" in features
    msisdn.supports_action_view_location = "ACTION_VIEW_LOCATION" in features
    msisdn.supports_payments_v1 = "PAYMENTS_V1" in features
    msisdn.save()


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3,
    ignore_result=True
)
def send_message(message_id):
    message = messaging.models.Message.objects.get(id=message_id)

    try:
        phonenumbers.parse(message.platform_conversation_id)
    except phonenumbers.phonenumberutil.NumberParseException:
        message.state = message.STATE_FAILED
        message.error_description = "Invalid MSISDN"
        message.save()
        return

    agent_obj = message.brand.rcs_agent

    base_url = f"https://{agent_obj.region}-rcsbusinessmessaging.googleapis.com"

    credentials = google.oauth2.service_account.Credentials.from_service_account_info(
        json.loads(agent_obj.service_account_key),
        scopes=SCOPES
    )
    session = google.auth.transport.requests.AuthorizedSession(credentials)

    msisdn = models.MSISDN.objects.filter(agent=agent_obj, msisdn=message.platform_conversation_id).first()
    if not msisdn:
        r = session.get(f"{base_url}/v1/phones/{message.platform_conversation_id}/capabilities?requestId={message.id}")
        if r.status_code == 404:
            msisdn = models.MSISDN(agent=agent_obj, msisdn=message.platform_conversation_id, supports_rcs=False)
            msisdn.save()
        else:
            r.raise_for_status()
            msisdn = models.MSISDN(agent=agent_obj, msisdn=message.platform_conversation_id, supports_rcs=True)
            update_msisdn_features(r.json().get("features", []), msisdn)

    if not msisdn.supports_rcs:
        message.state = message.STATE_FAILED
        message.error_description = "MSISDN does not support RCS"
        message.save()
        return

    body = {}

    if message.media_type == "chat_state":
        url = f"{base_url}/v1/phones/{message.platform_conversation_id}/agentEvents?eventId={message.id}"
        if "state" not in message.content:
            return
        if message.content["state"] == "composing":
            body["eventType"] = "IS_TYPING"
        elif message.content["state"] == "paused":
            return
        elif message.content["state"] == "representative_joined":
            return
        elif message.content["state"] == "representative_left":
            return
        else:
            message.state = message.STATE_FAILED
            message.error_description = "Invalid message"
            return
    else:
        body["contentMessage"] = {}
        url = f"{base_url}/v1/phones/{message.platform_conversation_id}/agentMessages?messageId={message.id}"
        if message.media_type == "text":
            body["contentMessage"]["text"] = message.content
        elif message.media_type == "rcs.card":
            body["contentMessage"]["richCard"] = message.content
        elif message.media_type == "file":
            if (f := map_file(message, message.content)) is not None:
                body["contentMessage"]["contentInfo"] = f
            else:
                return
        elif message.media_type == "select":
            if not ("media_type" in message.content and "options" in message.content and "content" in message.content):
                message.state = message.STATE_FAILED
                message.error_description = "Invalid message"
                message.save()
                return

            if message.content["media_type"] == "text":
                body["contentMessage"]["text"] = message.content["content"]
            elif message.content["media_type"] == "rcs.card":
                body["contentMessage"]["richCard"] = message.content["content"]
            elif message.content["media_type"] == "file":
                if (f := map_file(message, message.content["content"])) is not None:
                    body["contentMessage"]["contentInfo"] = f
                else:
                    return

            body["contentMessage"]["suggestions"] = []
            for option in message.content["options"]:
                if not ("media_type" in option and "content" in option):
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
                            "fallbackUrl": f'tel:{content["number"]}',
                            "dialAction": {
                                "phoneNumber": content["number"]
                            }
                        }
                    }
                elif option["media_type"] == "location":
                    content = option["content"]
                    if not ("lat_long" in content or "query" in content):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        return
                    if "query" in content:
                        query = urllib.parse.quote_plus(content["query"])
                        fallback_url = f"https://www.google.com/maps/search/?api=1&query={query}"
                    else:
                        lat_long = content['lat_long']
                        fallback_url = f"https://www.google.com/maps/search/?api=1&" \
                                       f"query={lat_long['latitude']},{lat_long['longitude']}"
                    suggestion = {
                        "action": {
                            "text": content["text"],
                            "postbackData": option.get("postback", content["text"]),
                            "fallbackUrl": fallback_url,
                            "viewLocationAction": {
                                "latLong": content.get("lat_long"),
                                "query": content.get("query"),
                            }
                        }
                    }
                elif option["media_type"] == "share_location":
                    suggestion = {
                        "action": {
                            "text": option["content"],
                            "postbackData": option.get("postback", option["content"]),
                            "shareLocationAction": {}
                        }
                    }
                elif option["media_type"] == "calendar_event":
                    content = option["content"]
                    if not (
                            "start_time" in content and "end_time" in content and
                            "title" in content and "description" in content
                    ):
                        message.state = message.STATE_FAILED
                        message.error_description = "Invalid message"
                        message.save()
                        return

                    fallback_url = messaging.tasks.make_calendar_fallback(message, content)

                    start_time = dateutil.parser.parse(content["start_time"])
                    end_time = dateutil.parser.parse(content["end_time"])

                    suggestion = {
                        "action": {
                            "text": option["content"]["text"],
                            "postbackData": option.get("postback", content["text"]),
                            "fallbackUrl": fallback_url,
                            "createCalendarEventAction": {
                                "startTime": start_time.astimezone(datetime.timezone.utc)
                                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "endTime": end_time.astimezone(datetime.timezone.utc)
                                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "title": content["title"],
                                "description": content["description"],
                            }
                        }
                    }
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
                    return

                body["contentMessage"]["suggestions"].append(suggestion)

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

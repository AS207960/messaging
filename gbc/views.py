from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import urllib.parse
from . import models
import os.path
import requests
import mimetypes
import messaging.models
import hmac
import base64
import binascii
import json
import dateutil.parser
import messaging.tasks


@csrf_exempt
@require_POST
def bm_webhook(request):
    if "X-Goog-Signature" not in request.headers:
        return HttpResponseBadRequest()

    goog_sig_b64 = request.headers["X-Goog-Signature"]
    try:
        goog_sig = base64.b64decode(goog_sig_b64)
    except binascii.Error:
        return HttpResponseBadRequest()

    own_sig = hmac.digest(settings.GBC_PARTNER_KEY.encode(), request.body, "sha512")
    if not hmac.compare_digest(goog_sig, own_sig):
        return HttpResponseForbidden()

    try:
        body_json = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    if messaging.models.Message.objects.filter(
            platform=messaging.models.Message.PLATFORM_GBM, platform_dedup_id=body_json["requestId"]
    ).first():
        return HttpResponse(status=200)

    agent_id = body_json["agent"]
    agent = models.BusinessMessagingAgent.objects.filter(google_id=agent_id).first()
    if not agent:
        return HttpResponse(status=200)

    entrypoint = body_json["context"].get("entryPoint")
    metadata = {
        "user_name": body_json["context"]["userInfo"].get("displayName"),
        "locale": body_json["context"].get("resolvedLocale"),
        "user_locale": body_json["context"]["userInfo"].get("userDeviceLocale"),
        "gbm.agent": agent_id,
        "gbm.place_id": body_json["context"].get("placeId"),
        "gbm.entrypoint": entrypoint if entrypoint != "ENTRY_POINT_UNSPECIFIED" else None,
    }

    timestamp = dateutil.parser.parse(body_json["sendTime"])

    new_message = messaging.models.Message(
        direction=messaging.models.Message.DIRECTION_INCOMING,
        brand=agent.brand.brand,
        platform=messaging.models.Message.PLATFORM_GBM,
        platform_conversation_id=body_json["conversationId"],
        platform_dedup_id=body_json["requestId"],
        client_message_id=None,
        timestamp=timestamp,
        metadata=metadata
    )

    if "message" in body_json:
        new_message.platform_message_id = body_json["message"]["name"]
        message_text = body_json["message"]["text"]
        is_img_url = False
        url_parts = None
        try:
            url_parts = urllib.parse.urlparse(message_text)
            if url_parts.netloc == "storage.googleapis.com":
                is_img_url = True
        except ValueError:
            is_img_url = False

        if not is_img_url:
            new_message.content = body_json["message"]["text"]
            new_message.media_type = "text"
        else:
            img = requests.get(message_text, stream=True)
            img.raise_for_status()
            img_name = os.path.basename(url_parts.path)
            img_path = default_storage.save(img_name, ContentFile(img.content))
            img_type = img.headers.get("content-type")
            if img_type:
                ext = mimetypes.guess_extension(img_type, strict=False)
            else:
                ext = ""
            img_url = settings.MEDIA_URL + img_path + ext
            new_message.content = {
                "url": img_url,
                "media_type": img_type
            }
            new_message.media_type = "file"
    elif "receipts" in body_json:
        for receipt in body_json["receipts"]["receipts"]:
            ref_message = messaging.models.Message.objects.filter(
                platform=messaging.models.Message.PLATFORM_GBM, platform_message_id=receipt["message"]
            ).first()
            if ref_message:
                if receipt["receiptType"] == "DELIVERED":
                    ref_message.state = messaging.models.Message.STATE_DELIVERED
                if receipt["receiptType"] == "READ":
                    ref_message.state = messaging.models.Message.STATE_READ
                new_metadata = ref_message.metadata if ref_message.metadata else {}
                new_metadata.update(metadata)
                ref_message.metadata = new_metadata
                ref_message.save()

            messaging.tasks.send_message.delay(ref_message.id)

        return HttpResponse(status=200)
    elif "userStatus" in body_json:
        if "isTyping" in body_json["userStatus"]:
            if body_json["userStatus"]["isTyping"]:
                new_message.media_type = "chat_state"
                new_message.content = {"state": "composing"}
            else:
                new_message.media_type = "chat_state"
                new_message.content = {"state": "paused"}
        elif "requestedLiveAgent" in body_json["userStatus"]:
            if body_json["userStatus"]["requestedLiveAgent"]:
                new_message.media_type = "chat_state"
                new_message.content = {"state": "request_live_agent"}
    elif "surveyResponse" in body_json:
        new_message.media_type = "gbm_survey"
        new_message.content = body_json["surveyResponse"]
    elif "suggestionResponse" in body_json:
        new_message.media_type = "postback"
        postback = body_json["suggestionResponse"]
        ref_message = messaging.models.Message.objects.filter(
            platform=messaging.models.Message.PLATFORM_GBM, platform_message_id=postback["message"]
        ).first()
        new_message.content = {
            "ref_message_id": (
                ref_message.client_message_id if ref_message.client_message_id else ref_message.id
            ) if ref_message else None,
            "data": postback["postbackData"],
            "text": postback["text"],
            "action_type": "reply" if postback["type"] == "REPLY" else (
                "action" if postback["type"] == "ACTION" else None)
        }

    new_message.save()
    messaging.tasks.process_message.delay(new_message.id)

    return HttpResponse(status=200)

from django.shortcuts import render, reverse, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import urllib.parse
from . import models, tasks
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
def rcs_webhook(request):
    try:
        body_json = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    if "clientToken" in body_json:
        if body_json["clientToken"] == settings.RCS_WEBHOOK_TOKEN:
            return HttpResponse(json.dumps({
                "secret": body_json.get("secret")
            }), status=200)
        else:
            return HttpResponseBadRequest()

    if "X-Goog-Signature" not in request.headers:
        return HttpResponseBadRequest()

    goog_sig_b64 = request.headers["X-Goog-Signature"]
    try:
        goog_sig = base64.b64decode(goog_sig_b64)
    except binascii.Error:
        return HttpResponseBadRequest()

    try:
        data_bytes = base64.b64decode(body_json["message"]["data"])
        data_json = json.loads(data_bytes.decode())
    except (binascii.Error, json.JSONDecodeError):
        return HttpResponseBadRequest()

    own_sig = hmac.digest(settings.RCS_WEBHOOK_TOKEN.encode(), data_bytes, "sha512")
    if not hmac.compare_digest(goog_sig, own_sig):
        return HttpResponseForbidden()

    subscription_id = body_json.get("subscription")
    data_type = body_json["message"]["attributes"]["type"]
    agent_obj = models.Agent.objects.filter(subscription_name=subscription_id).first()
    if not agent_obj:
        return HttpResponse(status=404)

    if data_type == "event":
        if messaging.models.Message.objects.filter(
                platform=messaging.models.Message.PLATFORM_RCS, platform_dedup_id=data_json["eventId"],
                platform_conversation_id=data_json["senderPhoneNumber"]
        ).first():
            return HttpResponse(status=202)

        print(data_json)
        timestamp = dateutil.parser.parse(data_json["sendTime"])

        if data_json["eventType"] == "IS_TYPING":
            new_message = messaging.models.Message(
                direction=messaging.models.Message.DIRECTION_INCOMING,
                brand=agent_obj.brand,
                platform=messaging.models.Message.PLATFORM_RCS,
                platform_conversation_id=data_json["senderPhoneNumber"],
                platform_dedup_id=data_json["eventId"],
                client_message_id=None,
                timestamp=timestamp,
                media_type="chat_state",
                content={"state": "composing"},
                metadata={}
            )
            new_message.save()
            messaging.tasks.process_message.delay(new_message.id)
        elif data_json["eventType"] in ("DELIVERED", "READ"):
            ref_message = messaging.models.Message.objects.filter(
                platform=messaging.models.Message.PLATFORM_RCS, id=data_json["messageId"]
            ).first()
            if ref_message:
                if data_json["eventType"] == "DELIVERED":
                    ref_message.state = messaging.models.Message.STATE_DELIVERED
                if data_json["eventType"] == "READ":
                    ref_message.state = messaging.models.Message.STATE_READ
                ref_message.save()
                messaging.tasks.send_message.delay(ref_message.id)

    elif data_type == "capabilities":
        msisdn, _ = models.MSISDN.objects.get_or_create(agent=agent_obj, msisdn=data_json["phoneNumber"])
        if data_json["rbmEnabled"]:
            msisdn.supports_rcs = True
            tasks.update_msisdn_features(data_json["features"], msisdn)
        else:
            msisdn.supports_rcs = True
            tasks.update_msisdn_features([], msisdn)

    elif data_type == "message":
        if messaging.models.Message.objects.filter(
                platform=messaging.models.Message.PLATFORM_RCS, platform_dedup_id=data_json["messageId"],
                platform_conversation_id=data_json["senderPhoneNumber"]
        ).first():
            return HttpResponse(status=202)

        print(data_json)
        timestamp = dateutil.parser.parse(data_json["sendTime"])

        new_message = messaging.models.Message(
            direction=messaging.models.Message.DIRECTION_INCOMING,
            brand=agent_obj.brand,
            platform=messaging.models.Message.PLATFORM_RCS,
            platform_conversation_id=data_json["senderPhoneNumber"],
            platform_dedup_id=data_json["messageId"],
            client_message_id=None,
            timestamp=timestamp,
            metadata={}
        )

        if "text" in data_json:
            new_message.content = data_json["text"]
            new_message.media_type = "text"
        elif "userFile" in data_json:
            file = requests.get(data_json["userFile"]["payload"]["fileUri"], stream=True)
            file.raise_for_status()
            file_name = data_json["userFile"]["payload"]["fileName"]
            file_type = data_json["userFile"]["payload"]["mimeType"]
            file_name_root, file_name_ext = os.path.splitext(file_name)
            print(file_name_root, file_name_ext)
            if not file_name_ext:
                file_name_ext = mimetypes.guess_extension(file_type, strict=False)
            file_name = file_name_root + file_name_ext
            file_path = default_storage.save(file_name, ContentFile(file.content))
            file_url = settings.MEDIA_URL + file_path
            new_message.content = {
                "url": file_url,
                "media_type": file_type,
                "title": None,
                "text": None
            }
            new_message.media_type = "file"
        elif "location" in data_json:
            new_message.content = data_json["location"]
            new_message.media_type = "location"
        elif "suggestionResponse" in data_json:
            new_message.content = data_json["suggestionResponse"]["text"]
            new_message.media_type = "text"
            new_message.metadata["postback_data"] = data_json["suggestionResponse"]["postbackData"]

        new_message.save()
        messaging.tasks.process_message.delay(new_message.id)

    return HttpResponse(status=202)

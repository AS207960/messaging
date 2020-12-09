from django.shortcuts import render, reverse, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_safe
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


@require_safe
def oauth_auth(request):
    if not (
        "client_id" in request.GET and "scope" in request.GET and "response_type" in request.GET
        and "redirect_uri" in request.GET and "state" in request.GET
    ):
        return HttpResponseBadRequest()

    if request.GET["scope"] != "as207960-messaging-oauth" or request.GET["response_type"] != "code":
        return HttpResponseBadRequest()

    redirect_uri = request.GET["redirect_uri"].strip()
    if redirect_uri not in (
        "https://business.google.com/callback",
        "https://business.google.com/callback?",
        "https://business.google.com/message?az-intent-type=1",
        "https://business.google.com/message?az-intent-type=1&",
    ):
        return HttpResponseBadRequest()

    gbc_brand = models.Brand.objects.filter(id=request.GET["client_id"]).first()
    if not gbc_brand:
        return HttpResponseBadRequest()
    brand = gbc_brand.brand

    if not brand.authorization_url or not brand.client_id:
        return HttpResponseBadRequest()

    oauth_state = models.OAuthState(
        google_state=request.GET["state"],
        redirect_uri=redirect_uri,
    )
    oauth_state.save()

    auth_url = brand.authorization_url
    auth_params = {
        "client_id": brand.client_id,
        "scope": "openid",
        "response_type": "code",
        "redirect_uri": settings.EXTERNAL_URL_BASE + reverse('messaging:messaging_oauth_redirect'),
        "state": str(oauth_state.id),
    }
    url_parts = list(urllib.parse.urlparse(auth_url))
    query_parts = dict(urllib.parse.parse_qsl(url_parts[4]))
    query_parts.update(auth_params)
    url_parts[4] = urllib.parse.urlencode(query_parts)
    redirect_uri = urllib.parse.urlunparse(url_parts)

    return redirect(redirect_uri)


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
            img_type = img.headers.get("content-type")
            if img_type:
                ext = mimetypes.guess_extension(img_type, strict=False)
            else:
                ext = ""
            img_path = default_storage.save(img_name + ext, ContentFile(img.content))
            img_url = settings.MEDIA_URL + img_path
            new_message.content = {
                "url": img_url,
                "media_type": img_type,
                "title": None,
                "text": None
            }
            new_message.media_type = "file"
    elif "suggestionResponse" in body_json:
        response = body_json["suggestionResponse"]
        ref_message = messaging.models.Message.objects.filter(
            platform=messaging.models.Message.PLATFORM_GBM, platform_message_id=response["message"]
        ).first()
        if ref_message:
            new_message.metadata["ref_message_id"] = \
                ref_message.client_message_id if ref_message.client_message_id else ref_message.id
        if response["type"] == "REPLY":
            new_message.content = response["text"]
            new_message.media_type = "text"
            new_message.metadata["postback_data"] = response["postbackData"]
        elif response["type"] == "ACTION":
            new_message.content = {
                "text": response["text"],
                "postback_data": response["postbackData"]
            }
            new_message.media_type = "action_postback"
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
    elif "authenticationResponse" is body_json:
        if body_json["authenticationResponse"].get("code"):
            state = models.OAuthState.objects.filter(id=str(body_json["authenticationResponse"]["code"])).first()
            if state:
                new_message.media_type = "oauth_code"
                new_message.content = state.auth_code
            else:
                return HttpResponse(status=200)
        elif body_json["authenticationResponse"].get("errorDetails", {}).get("error"):
            new_message.media_type = "oauth_error"
            new_message.content = body_json["authenticationResponse"]["errorDetails"]["error"]
        else:
            return HttpResponse(status=200)

    new_message.save()
    messaging.tasks.process_message.delay(new_message.id)

    return HttpResponse(status=200)

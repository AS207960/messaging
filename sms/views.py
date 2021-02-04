from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import twilio.request_validator
import twilio.rest
import twilio.twiml.messaging_response
import messaging.models
import messaging.tasks
import rcs.tasks
from . import models


def check_auth(f):
    def new_f(request, *args, **kwargs):
        account_sid = request.POST.get("AccountSid")
        if not account_sid:
            return HttpResponseBadRequest()

        twilio_account = models.TwilioAccount.objects.filter(account_sid=account_sid).first()
        if not twilio_account:
            return HttpResponseBadRequest()

        twilio_validator = twilio.request_validator.RequestValidator(twilio_account.account_token)

        uri = f"https://{request.get_host()}{request.path}"
        sig_valid = twilio_validator.validate(
            uri, request.POST, request.META.get("HTTP_X_TWILIO_SIGNATURE")
        )
        if not sig_valid:
            return HttpResponseForbidden()

        return f(request, *args, **kwargs)

    return new_f


@csrf_exempt
@require_POST
@check_auth
def twilio_webhook(request):
    msg_from = request.POST.get("From")
    msg_to = request.POST.get("To")
    msg_id = request.POST.get("MessageSid")
    msg_body = request.POST.get("Body")
    agent_obj = models.Agent.objects.filter(msisdn=msg_to).first()
    if not agent_obj:
        return HttpResponse(status=404)

    rcs.tasks.attempt_update_msisdn.delay(agent_obj.brand.id, msg_from)

    response = str(twilio.twiml.messaging_response.MessagingResponse())

    if messaging.models.Message.objects.filter(
            platform=messaging.models.Message.PLATFORM_MSISDN,
            platform_dedup_id=f"sms-message:{msg_id}",
    ).first():
        return HttpResponse(response)

    new_message = messaging.models.Message(
        direction=messaging.models.Message.DIRECTION_INCOMING,
        brand=agent_obj.brand,
        platform=messaging.models.Message.PLATFORM_MSISDN,
        platform_conversation_id=msg_from,
        platform_dedup_id=f"sms-message:{msg_id}",
        client_message_id=None,
        timestamp=timezone.now(),
        metadata={
            "msisdn.transport": "sms"
        },
        content=msg_body,
        media_type="text",
    )
    new_message.save()
    messaging.tasks.process_message.delay(new_message.id)

    return HttpResponse(response)


@csrf_exempt
@require_POST
@check_auth
def twilio_status_webhook(request):
    msg_id = request.POST.get("MessageSid")
    msg_status = request.POST.get("MessageStatus")
    message = messaging.models.Message.objects.filter(
        platform=messaging.models.Message.PLATFORM_MSISDN,
        platform_message_id=msg_id,
    ).first()  # type: messaging.models.Message

    if not message:
        return HttpResponse(status=202)

    if msg_status == "delivered":
        message.state = message.STATE_DELIVERED
    elif msg_status == "read":
        message.state = message.STATE_READ
    elif msg_status == "failed":
        message.state = message.STATE_FAILED
        message.error_description = "Message delivery failed"

    message.save()
    messaging.tasks.send_message.delay(message.id)

    return HttpResponse(status=202)


@csrf_exempt
@require_POST
def vsms_postback_webhook(request):
    print(request.headers, request.body)

    return HttpResponse(status=202)

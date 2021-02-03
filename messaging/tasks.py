from celery import shared_task
from . import models
from .api import serializers
from django.conf import settings
from django.shortcuts import reverse
import gbc.tasks
import rcs.tasks
import collections
import json
import hmac
import requests
import dateutil.parser
import base64


def make_calendar_fallback(message, content):
    if not (
            "start_time" in content and "end_time" in content and
            "title" in content and "description" in content and
            "text" in content
    ):
        message.state = message.STATE_FAILED
        message.error_description = "Invalid message"
        message.save()
        return

    try:
        start_time = dateutil.parser.parse(content["start_time"])
        end_time = dateutil.parser.parse(content["end_time"])
    except dateutil.parser.ParserError:
        message.state = message.STATE_FAILED
        message.error_description = "Invalid message"
        message.save()
        return
    calendar_data = base64.urlsafe_b64encode(json.dumps({
        "start": int(start_time.timestamp()),
        "end": int(end_time.timestamp()),
        "title": content["title"],
        "description": content["description"]
    }).encode()).decode()
    return settings.EXTERNAL_URL_BASE + reverse('messaging:calendar_event', args=(calendar_data,))


@shared_task(ignore_result=True)
def process_message(message_id):
    message = models.Message.objects.get(id=message_id)

    if message.direction == message.DIRECTION_OUTGOING:
        if message.platform == message.PLATFORM_GBM:
            gbc.tasks.send_message.delay(message.id)
        elif message.platform == message.PLATFORM_RCS:
            rcs.tasks.send_message.delay(message.id)
    elif message.direction == message.DIRECTION_INCOMING:
        send_message.delay(message.id)


class FakeRequest:
    GET = {}

    @property
    def auth(self):
        return collections.namedtuple("Auth", ["token"])(token=None)

    @staticmethod
    def build_absolute_uri(url):
        return settings.EXTERNAL_URL_BASE + url


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3,
    ignore_result=True
)
def send_message(message_id):
    message = models.Message.objects.get(id=message_id)

    if message.brand.webhook_url:
        representative = serializers.MessageSerializer(instance=message, context={
            "view": collections.namedtuple("View", ['kwargs'])(kwargs={
                "brand_pk": message.brand.id
            }),
            "request": FakeRequest()
        })

        post_data = json.dumps(representative.data).encode()
        post_hmac = hmac.new(message.brand.webhook_signing_secret.encode(), digestmod="sha512")
        post_hmac.update(post_data)
        post_sig = post_hmac.hexdigest()

        r = requests.post(message.brand.webhook_url, headers={
            "X-AS207960-Signature-SHA512": post_sig,
            "Content-Type": "application/json",
            "User-Agent": "AS207960 Messaging Service"
        }, data=post_data)
        r.raise_for_status()
        message.status = message.STATE_DISPATCHED
        message.save()

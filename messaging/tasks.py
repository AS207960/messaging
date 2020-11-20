from celery import shared_task
from . import models
from .api import serializers
from django.conf import settings
import gbc.tasks
import collections
import json
import hmac
import requests


@shared_task
def process_message(message_id):
    message = models.Message.objects.get(id=message_id)

    if message.direction == message.DIRECTION_OUTGOING:
        if message.platform == message.PLATFORM_GBM:
            gbc.tasks.send_message.delay(message.id)
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
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3
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
            "X-AS207960-Signature-SHA512": post_sig
        }, body=post_data)
        r.raise_for_status()

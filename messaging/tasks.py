from celery import shared_task
from . import models
import gbc.tasks


@shared_task
def process_message(message_id):
    message = models.Message.objects.get(id=message_id)

    if message.direction == message.DIRECTION_OUTGOING:
        if message.platform == message.PLATFORM_GBM:
            gbc.tasks.send_message.delay(message.id)

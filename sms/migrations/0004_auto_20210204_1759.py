# Generated by Django 3.1.6 on 2021-02-04 17:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0003_msisdn'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='vsms_agent_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='agent',
            name='vsms_private_key',
            field=models.TextField(blank=True, null=True),
        ),
    ]
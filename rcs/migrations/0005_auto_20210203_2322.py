# Generated by Django 3.1.6 on 2021-02-03 23:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rcs', '0004_msidn_agent'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='msidn',
            options={'verbose_name': 'MSIDN', 'verbose_name_plural': 'MSIDNs'},
        ),
    ]
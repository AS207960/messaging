# Generated by Django 3.1.6 on 2021-02-03 23:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rcs', '0006_auto_20210203_2322'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='MSIDN',
            new_name='MSISDN',
        ),
        migrations.AlterModelOptions(
            name='msisdn',
            options={'verbose_name': 'MSISDN', 'verbose_name_plural': 'MSISDNs'},
        ),
    ]

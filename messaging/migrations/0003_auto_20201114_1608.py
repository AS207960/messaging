# Generated by Django 3.1.3 on 2020-11-14 16:08

import as207960_utils.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_auto_20201114_1427'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='message',
            name='error_code',
        ),
        migrations.CreateModel(
            name='Representative',
            fields=[
                ('id', as207960_utils.models.TypedUUIDField(data_type='messaging_representative', primary_key=True, serialize=False)),
                ('is_bot', models.BooleanField(blank=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='messaging.brand')),
            ],
        ),
        migrations.AddField(
            model_name='message',
            name='representative',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='messaging.representative'),
        ),
    ]

# Generated by Django 4.0.2 on 2022-06-27 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basic_ui', '0016_alter_basicblockset_identifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='basicblockentry',
            name='measurement_results',
            field=models.JSONField(default={}),
            preserve_default=False,
        ),
    ]

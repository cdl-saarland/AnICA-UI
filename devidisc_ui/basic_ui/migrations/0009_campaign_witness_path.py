# Generated by Django 3.2.6 on 2021-09-27 13:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basic_ui', '0008_discovery_generality'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='witness_path',
            field=models.CharField(default='foo', max_length=2048),
            preserve_default=False,
        ),
    ]

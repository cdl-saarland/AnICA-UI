# Generated by Django 4.0.2 on 2022-03-07 13:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basic_ui', '0005_remove_discovery_ab_coverage'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='tag',
            field=models.CharField(default='default-tag', max_length=255),
            preserve_default=False,
        ),
    ]
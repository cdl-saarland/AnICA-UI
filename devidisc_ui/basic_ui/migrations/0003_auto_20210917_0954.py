# Generated by Django 3.2.6 on 2021-09-17 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basic_ui', '0002_auto_20210916_1530'),
    ]

    operations = [
        migrations.AddField(
            model_name='discoverybatch',
            name='num_interesting',
            field=models.IntegerField(default=42),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='discoverybatch',
            name='num_sampled',
            field=models.IntegerField(default=42),
            preserve_default=False,
        ),
    ]
# Generated by Django 4.0.2 on 2022-06-27 08:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basic_ui', '0015_remove_basicblockentry_covered_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basicblockset',
            name='identifier',
            field=models.CharField(max_length=256, unique=True),
        ),
    ]
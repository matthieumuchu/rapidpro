# Generated by Django 1.10.5 on 2017-04-28 19:35

from django.db import migrations
import temba.utils.models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0091_exportmessagestask_system_label")]

    operations = [
        migrations.AddField(
            model_name="broadcast",
            name="media",
            field=temba.utils.models.TranslatableField(
                help_text="The localized versions of the media", max_length=255, null=True, verbose_name="Media"
            ),
        ),
        migrations.AddField(
            model_name="broadcast",
            name="translations",
            field=temba.utils.models.TranslatableField(
                help_text="The localized versions of the message text",
                max_length=640,
                null=True,
                verbose_name="Translations",
            ),
        ),
    ]

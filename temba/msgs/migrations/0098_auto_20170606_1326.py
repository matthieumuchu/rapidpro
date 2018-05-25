# Generated by Django 1.10.5 on 2017-06-06 13:26

from django.db import migrations, models
import temba.utils.models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0097_remove_msg_media")]

    operations = [
        migrations.AlterField(
            model_name="broadcast",
            name="text",
            field=temba.utils.models.TranslatableField(
                help_text="The localized versions of the message text", max_length=8000, verbose_name="Translations"
            ),
        ),
        migrations.AlterField(
            model_name="msg",
            name="text",
            field=models.TextField(help_text="The actual message content that was sent", verbose_name="Text"),
        ),
    ]

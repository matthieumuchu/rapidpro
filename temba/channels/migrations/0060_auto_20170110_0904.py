# Generated by Django 1.9.12 on 2017-01-10 09:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("channels", "0059_update_nexmo_channels_roles")]

    operations = [
        migrations.AddField(
            model_name="channellog",
            name="session",
            field=models.ForeignKey(
                help_text="The channel session for this log",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="channel_logs",
                to="channels.ChannelSession",
            ),
        ),
        migrations.AlterField(
            model_name="channellog",
            name="msg",
            field=models.ForeignKey(
                help_text="The message that was sent",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="channel_logs",
                to="msgs.Msg",
            ),
        ),
    ]

# Generated by Django 1.10.5 on 2017-01-18 08:12

from django.db import migrations, models
from temba.sql import InstallSQL


class Migration(migrations.Migration):

    dependencies = [("flows", "0085_auto_20170112_1629")]

    operations = [
        migrations.AddField(
            model_name="flowpathcount",
            name="is_squashed",
            field=models.BooleanField(default=False, help_text="Whether this row was created by squashing"),
        ),
        migrations.AddField(
            model_name="flowruncount",
            name="is_squashed",
            field=models.BooleanField(default=False, help_text="Whether this row was created by squashing"),
        ),
        migrations.RunSQL(
            "CREATE INDEX flows_flowpathcount_unsquashed "
            "ON flows_flowpathcount(flow_id, from_uuid, to_uuid, period) WHERE NOT is_squashed"
        ),
        migrations.RunSQL(
            "CREATE INDEX flows_flowruncount_unsquashed "
            "ON flows_flowruncount(flow_id, exit_type) WHERE NOT is_squashed"
        ),
        InstallSQL("0086_flows"),
    ]

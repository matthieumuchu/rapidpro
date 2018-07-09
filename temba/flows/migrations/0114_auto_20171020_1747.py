# Generated by Django 1.11.2 on 2017-10-20 17:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0067_auto_20170808_1852"), ("flows", "0113_backfill_value_type")]

    operations = [
        migrations.AddField(
            model_name="flow",
            name="field_dependencies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Any fields this flow depends on",
                related_name="dependent_flows",
                to="contacts.ContactField",
                verbose_name="",
            ),
        ),
        migrations.AddField(
            model_name="flow",
            name="flow_dependencies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Any flows this flow uses",
                related_name="dependent_flows",
                to="flows.Flow",
                verbose_name="Flow Dependencies",
            ),
        ),
        migrations.AddField(
            model_name="flow",
            name="group_dependencies",
            field=models.ManyToManyField(
                blank=True,
                help_text="Any groups this flow uses",
                related_name="dependent_flows",
                to="contacts.ContactGroup",
                verbose_name="Group Dependencies",
            ),
        ),
    ]

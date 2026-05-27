from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dash", "0006_lead_google_adgroup_id_lead_google_campaign_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="calllog",
            name="recording",
            field=models.FileField(blank=True, null=True, upload_to="recordings/"),
        ),
    ]

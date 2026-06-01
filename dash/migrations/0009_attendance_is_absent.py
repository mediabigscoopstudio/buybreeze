from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dash', '0008_systemapisettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='is_absent',
            field=models.BooleanField(default=False),
        ),
    ]

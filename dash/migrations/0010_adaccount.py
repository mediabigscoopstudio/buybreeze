from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dash', '0009_attendance_is_absent'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('meta', 'Meta / Facebook Ads'), ('google', 'Google Ads')], max_length=20)),
                ('name', models.CharField(max_length=255)),
                ('account_id', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Ad Account',
                'verbose_name_plural': 'Ad Accounts',
                'ordering': ['platform', 'name'],
            },
        ),
    ]

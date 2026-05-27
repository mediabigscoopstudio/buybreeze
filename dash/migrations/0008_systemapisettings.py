from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dash', '0007_calllog_recording'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemAPISettings',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key',         models.CharField(max_length=100, unique=True)),
                ('value',       models.TextField(blank=True, default='')),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('updated_at',  models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name':        'API Setting',
                'verbose_name_plural': 'API Settings',
            },
        ),
    ]

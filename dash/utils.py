from .models import SystemAPISettings


def get_setting(key, default=''):
    try:
        return SystemAPISettings.objects.get(key=key).value or default
    except SystemAPISettings.DoesNotExist:
        return default


API_KEY_DEFAULTS = [
    ('META_APP_ID',              'Meta / Facebook App ID'),
    ('META_APP_SECRET',          'Meta / Facebook App Secret'),
    ('META_AD_ACCOUNT_ID',       'Meta Ad Account ID (act_XXXXXXXXX)'),
    ('META_ACCESS_TOKEN',        'Meta Long-lived Access Token'),
    ('GOOGLE_DEVELOPER_TOKEN',   'Google Ads Developer Token'),
    ('GOOGLE_CLIENT_ID',         'Google OAuth2 Client ID'),
    ('GOOGLE_CLIENT_SECRET',     'Google OAuth2 Client Secret'),
    ('GOOGLE_REFRESH_TOKEN',     'Google OAuth2 Refresh Token'),
    ('GOOGLE_CUSTOMER_ID',       'Google Ads Customer ID (without dashes)'),
    ('WHATSAPP_API_KEY',         'WhatsApp Cloud API Bearer Token'),
    ('WHATSAPP_PHONE_NUMBER_ID', 'WhatsApp Phone Number ID'),
    ('FAST2SMS_API_KEY',         'Fast2SMS API Key'),
]


def ensure_api_settings():
    for key, description in API_KEY_DEFAULTS:
        SystemAPISettings.objects.get_or_create(
            key=key,
            defaults={'description': description, 'value': ''},
        )

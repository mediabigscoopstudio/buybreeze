"""
Meta / Facebook Ads helpers.
Requires: pip install facebook-business
"""
from .utils import get_setting


def _get_api():
    from facebook_business.api import FacebookAdsApi
    from facebook_business.exceptions import FacebookRequestError

    app_id      = get_setting('META_APP_ID')
    app_secret  = get_setting('META_APP_SECRET')
    access_token = get_setting('META_ACCESS_TOKEN')

    if not all([app_id, app_secret, access_token]):
        raise ValueError('Meta API credentials are not fully configured.')

    FacebookAdsApi.init(app_id, app_secret, access_token)
    return access_token


def get_meta_campaigns(date_preset='last_30d', account_id=None):
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign

    _get_api()
    if not account_id:
        account_id = get_setting('META_AD_ACCOUNT_ID')
    if not account_id:
        raise ValueError('No Meta Ad Account ID configured.')

    account = AdAccount(account_id)
    campaigns = account.get_campaigns(
        fields=[
            Campaign.Field.name,
            Campaign.Field.status,
            Campaign.Field.objective,
            Campaign.Field.daily_budget,
            Campaign.Field.lifetime_budget,
        ],
        params={'date_preset': date_preset, 'limit': 100},
    )

    results = []
    for c in campaigns:
        results.append({
            'id':              c.get('id', ''),
            'name':            c.get('name', ''),
            'status':          c.get('status', ''),
            'objective':       c.get('objective', ''),
            'daily_budget':    int(c.get('daily_budget', 0)) / 100,
            'lifetime_budget': int(c.get('lifetime_budget', 0)) / 100,
        })
    return results


def get_meta_leads(limit=50, account_id=None):
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.lead import Lead

    _get_api()
    if not account_id:
        account_id = get_setting('META_AD_ACCOUNT_ID')
    if not account_id:
        raise ValueError('No Meta Ad Account ID configured.')

    account = AdAccount(account_id)
    lead_forms = account.get_ad_leads(
        fields=['created_time', 'field_data', 'ad_name', 'form_id'],
        params={'limit': limit},
    )

    results = []
    for lead in lead_forms:
        fields = {f['name']: (f['values'][0] if f.get('values') else '') for f in lead.get('field_data', [])}
        results.append({
            'created_time': lead.get('created_time', ''),
            'name':         fields.get('full_name', fields.get('name', '—')),
            'phone':        fields.get('phone_number', fields.get('phone', '—')),
            'email':        fields.get('email', '—'),
            'ad_name':      lead.get('ad_name', '—'),
        })
    return results

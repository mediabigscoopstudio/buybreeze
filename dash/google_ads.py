"""
Google Ads helpers.
Requires: pip install google-ads
"""
from .utils import get_setting


def _build_client():
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        'developer_token':  get_setting('GOOGLE_DEVELOPER_TOKEN'),
        'client_id':        get_setting('GOOGLE_CLIENT_ID'),
        'client_secret':    get_setting('GOOGLE_CLIENT_SECRET'),
        'refresh_token':    get_setting('GOOGLE_REFRESH_TOKEN'),
        'use_proto_plus':   True,
    }
    login_customer_id = get_setting('GOOGLE_CUSTOMER_ID')
    if login_customer_id:
        config['login_customer_id'] = login_customer_id

    return GoogleAdsClient.load_from_dict(config)


def get_google_campaigns(date_range='LAST_30_DAYS'):
    client      = _build_client()
    customer_id = get_setting('GOOGLE_CUSTOMER_ID').replace('-', '')

    ga_service = client.get_service('GoogleAdsService')
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    results = []
    for row in response:
        results.append({
            'id':           row.campaign.id,
            'name':         row.campaign.name,
            'status':       row.campaign.status.name,
            'channel':      row.campaign.advertising_channel_type.name,
            'impressions':  row.metrics.impressions,
            'clicks':       row.metrics.clicks,
            'cost':         round(row.metrics.cost_micros / 1_000_000, 2),
            'conversions':  round(row.metrics.conversions, 2),
            'ctr':          round((row.metrics.clicks / row.metrics.impressions * 100), 2)
                            if row.metrics.impressions else 0,
        })
    return results

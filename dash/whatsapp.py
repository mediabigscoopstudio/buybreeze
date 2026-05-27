"""
WhatsApp Business Cloud API helpers.
No extra package needed — uses standard urllib / requests.
"""
import json
import urllib.request
import urllib.error

from .utils import get_setting


def _headers():
    return {
        'Authorization': f"Bearer {get_setting('WHATSAPP_API_KEY')}",
        'Content-Type':  'application/json',
    }


def _phone_number_id():
    return get_setting('WHATSAPP_PHONE_NUMBER_ID')


def get_whatsapp_templates():
    """Return a list of approved message templates."""
    phone_number_id = _phone_number_id()
    # Fetch templates via the Business Account — derive waba_id from phone number info first
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}?fields=name,display_phone_number,verified_name"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"WhatsApp API error {e.code}: {e.read().decode()}")

    # Return basic info as templates list for display; real template listing
    # requires the WABA ID which is separate from the phone number ID.
    return [{'name': data.get('name', ''), 'display_phone_number': data.get('display_phone_number', '')}]


def send_whatsapp_message(to_phone: str, template_name: str, language_code: str = 'en_US') -> dict:
    """
    Send a template message via WhatsApp Cloud API.
    to_phone: international format without '+', e.g. '919876543210'
    """
    phone_number_id = _phone_number_id()
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = json.dumps({
        'messaging_product': 'whatsapp',
        'to':                to_phone,
        'type':              'template',
        'template': {
            'name':     template_name,
            'language': {'code': language_code},
        },
    }).encode()

    req = urllib.request.Request(url, data=payload, headers=_headers(), method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"WhatsApp send error {e.code}: {e.read().decode()}")

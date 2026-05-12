import random
import requests
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp(phone_number, otp):

    # =========================================
    # TEST MODE
    # =========================================
    if settings.OTP_TEST_MODE:

        print("\n===================================")
        print("        OTP TEST MODE")
        print("===================================")
        print(f"PHONE NUMBER : {phone_number}")
        print(f"OTP CODE     : {otp}")
        print("===================================\n")

        return True

    # =========================================
    # PRODUCTION MODE
    # =========================================
    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        'route': 'otp',
        'variables_values': otp,
        'numbers': phone_number,
    }

    headers = {
        'authorization': settings.FAST2SMS_API_KEY
    }

    response = requests.get(
        url,
        params=payload,
        headers=headers
    )

    print(response.json())

    return response.status_code == 200
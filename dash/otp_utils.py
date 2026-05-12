import random
import requests

from django.conf import settings


# ============================================================
# GENERATE OTP
# ============================================================
def generate_otp():

    return str(random.randint(100000, 999999))


# ============================================================
# SEND OTP
# ============================================================
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
    # LIVE FAST2SMS MODE
    # =========================================
    try:

        url = "https://www.fast2sms.com/dev/bulkV2"

        payload = {
            'authorization': settings.FAST2SMS_API_KEY,
            'variables_values': otp,
            'route': 'otp',
            'numbers': phone_number,
        }

        headers = {
            'cache-control': "no-cache"
        }

        response = requests.get(
            url,
            params=payload,
            headers=headers
        )

        data = response.json()

        print("\n===================================")
        print("      FAST2SMS RESPONSE")
        print("===================================")
        print(data)
        print("===================================\n")

        # =====================================
        # SUCCESS CHECK
        # =====================================
        if data.get('return') == True:

            return True

        return False

    except Exception as e:

        print("\n===================================")
        print("        OTP ERROR")
        print("===================================")
        print(str(e))
        print("===================================\n")

        return False
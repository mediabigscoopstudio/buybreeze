from django.conf import settings


# =========================================
# GENERATE OTP
# =========================================
def generate_otp():

    # =====================================
    # DEMO / TEST MODE
    # =====================================
    if settings.OTP_TEST_MODE:
        return "000000"

    # =====================================
    # LIVE MODE
    # =====================================
    import random

    return str(random.randint(100000, 999999))


# =========================================
# SEND OTP
# =========================================
def send_otp(phone_number, otp):

    # =====================================
    # TEST MODE
    # =====================================
    if settings.OTP_TEST_MODE:

        print("\n===================================")
        print("        DEMO OTP MODE")
        print("===================================")
        print(f"PHONE NUMBER : {phone_number}")
        print(f"OTP CODE     : {otp}")
        print("===================================\n")

        return True

    # =====================================
    # LIVE FAST2SMS MODE
    # =====================================
    try:

        import requests

        url = "https://www.fast2sms.com/dev/bulkV2"

        payload = {
            'sender_id': 'FSTSMS',
            'message': f'Your BuyBuzz Infra OTP is {otp}',
            'language': 'english',
            'route': 'q',
            'numbers': phone_number,
        }

        headers = {
            'authorization': settings.FAST2SMS_API_KEY
        }

        response = requests.post(
            url,
            data=payload,
            headers=headers
        )

        data = response.json()

        print("\n===================================")
        print("      FAST2SMS RESPONSE")
        print("===================================")
        print(data)
        print("===================================\n")

        return response.status_code == 200

    except Exception as e:

        print("\n===================================")
        print("        OTP ERROR")
        print("===================================")
        print(str(e))
        print("===================================\n")

        return False
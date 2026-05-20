import json
import random
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from decouple import config

FAST2SMS_API_KEY = config('FAST2SMS_API_KEY')
OTP_TEST_MODE = config('OTP_TEST_MODE', default= True, cast=bool)


def send_otp(phone, otp):
    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "route": "otp",
        "variables_values": otp,
        "numbers": phone
    }

    headers = {
        "authorization": FAST2SMS_API_KEY
    }

    requests.get(url, params=payload, headers=headers)


@csrf_exempt
def employee_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = json.loads(request.body)
    phone = data.get("phone")

    if not phone:
        return JsonResponse({"success": False, "message": "Phone required"})

    try:
        user = User.objects.get(username=phone)

    except User.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Employee not found"
        })

    #otp = str(random.randint(100000, 999999)) change during production
    otp = 000000
    request.session["otp"] = otp
    request.session["phone"] = phone

    send_otp(phone, otp)

    return JsonResponse({
        "success": True,
        "message": "OTP sent"
    })


@csrf_exempt
def verify_employee_otp(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    data = json.loads(request.body)
    otp = data.get("otp")
    phone = data.get("phone")

    saved_otp = request.session.get("otp")
    saved_phone = request.session.get("phone")

    if otp != saved_otp or phone != saved_phone:
        return JsonResponse({
            "success": False,
            "message": "Invalid OTP"
        })

    user = User.objects.get(username=phone)

    return JsonResponse({
        "success": True,
        "employee_id": user.id,
        "name": user.username,
    })
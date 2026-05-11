from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import HttpResponse

@csrf_exempt
def meta_webhook(request):

    # Meta verification
    if request.method == "GET":

        VERIFY_TOKEN = "buybreeze_meta_verify"

        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge)

        return HttpResponse("Verification failed", status=403)

    # Incoming leads
    if request.method == "POST":

        data = json.loads(request.body)

        print("META WEBHOOK DATA:", data)

        return JsonResponse({
            "status": "received"
        })
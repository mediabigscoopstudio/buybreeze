import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'corecrm.settings')
django.setup()

from django.contrib.auth.models import User

if len(sys.argv) < 3:
    print("Usage: python change_password.py <username> <new_password>")
    exit()

username = sys.argv[1]
new_password = sys.argv[2]

try:
    user = User.objects.get(username=username)
    user.set_password(new_password)
    user.save()

    print(f"✅ Password updated for {username}")

except User.DoesNotExist:
    print("❌ User not found")

# python change_password.py vaibhav 12345
import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'corecrm.settings')
django.setup()

from django.contrib.auth.models import User
from dash.models import Branch, UserProfile

# =========================
# DATA
# =========================

branches = [
    ("Delhi Central", "Delhi"),
    ("Gurugram Hub", "Gurugram"),
    ("Noida Tech Park", "Noida"),
    ("Jaipur Office", "Jaipur"),
    ("Chandigarh Office", "Chandigarh"),
]

names = [
    "Rahul Sharma","Amit Verma","Sandeep Singh","Vikas Gupta","Ankit Jain",
    "Rohit Mehta","Karan Malhotra","Deepak Yadav","Nikhil Bansal","Varun Arora",
    "Manish Kapoor","Saurabh Gupta","Tarun Khanna","Gaurav Sharma","Abhishek Singh",
    "Puneet Jain","Harsh Vardhan","Arjun Patel","Vivek Tiwari","Mohit Aggarwal",
    "Rajat Bhatia","Kunal Sethi","Ashish Choudhary","Sumit Saxena","Aditya Srivastava",
    "Riya Sharma","Neha Verma","Priya Singh","Pooja Gupta","Anjali Mehta",
    "Sneha Kapoor","Kavya Jain","Isha Arora","Nidhi Yadav","Simran Kaur",
    "Aarti Mishra","Divya Agarwal","Payal Saxena","Megha Tiwari","Shreya Bansal"
]

name_index = 0

# =========================
# HELPERS
# =========================

def split_name(full):
    parts = full.split()
    return parts[0], parts[-1] if len(parts) > 1 else ""

def create_user(full_name):
    global name_index

    first, last = split_name(full_name)
    username = f"{first.lower()}{name_index}"
    email = f"{first.lower()}.{last.lower()}@gmail.com"

    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first,
            "last_name": last,
            "email": email,
            "is_active": True,
            "is_staff": True,
        }
    )

    user.set_password("12345")
    user.save()

    name_index += 1
    return user

def create_profile(user, role, branch, reports_to=None):
    phone = f"9{random.randint(100000000,999999999)}"

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "role": role,
            "branch": branch,
            "reports_to": reports_to,
            "phone": phone,
            "status": "Enabled"
        }
    )
    return profile

# =========================
# MAIN LOGIC
# =========================

print("🚀 Creating structured hierarchy...")

for branch_name, location in branches:

    # 1. CREATE BRANCH
    branch, _ = Branch.objects.get_or_create(
        name=branch_name,
        defaults={
            "location": location,
            "address": f"{location} Office",
            "phone": "9999999999",
            "email": f"{location.lower()}@company.com",
            "gps_radius": 10,
            "status": "Enabled"
        }
    )

    print(f"\n📍 Branch: {branch_name}")

    # 2. CREATE MANAGER
    manager_name = names[name_index % len(names)]
    manager_user = create_user(manager_name)

    manager = create_profile(
        manager_user,
        "manager",
        branch,
        reports_to=None   # ✅ IMPORTANT
    )

    print(f"  👤 Manager: {manager_name}")

    # 3. CREATE 5 TLs
    for i in range(5):

        tl_name = names[name_index % len(names)]
        tl_user = create_user(tl_name)

        tl = create_profile(
            tl_user,
            "tl",
            branch,
            reports_to=manager   # ✅ TL → Manager
        )

        print(f"    👨‍💼 TL: {tl_name}")

        # 4. CREATE 6–7 EMPLOYEES FOR EACH TL
        for j in range(random.randint(6, 7)):

            emp_name = names[name_index % len(names)]
            emp_user = create_user(emp_name)

            create_profile(
                emp_user,
                "employee",
                branch,
                reports_to=tl   # ✅ Employee → TL
            )

        print(f"       ↳ {j+1} employees assigned")

print("\n✅ DONE — Perfect hierarchy created")
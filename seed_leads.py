import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'corecrm.settings')
django.setup()

from dash.models import Lead, Branch

# =========================
# DATA
# =========================

names = [
    "Rohit Sharma","Amit Verma","Sandeep Singh","Vikas Gupta","Ankit Jain",
    "Riya Sharma","Neha Verma","Priya Singh","Pooja Gupta","Anjali Mehta",
    "Sneha Kapoor","Kavya Jain","Isha Arora","Nidhi Yadav","Simran Kaur",
    "Aarti Mishra","Divya Agarwal","Payal Saxena","Megha Tiwari","Shreya Bansal",
    "Rahul Tiwari","Aditya Srivastava","Deepak Yadav","Karan Malhotra","Rajat Bhatia",
    "Kunal Sethi","Ashish Choudhary","Sumit Saxena","Harsh Vardhan","Arjun Patel"
]

sources = ['meta', 'google', 'manual']

campaigns = [
    "Summer Sale Campaign",
    "Luxury Homes Campaign",
    "Festive Offer Campaign",
    "NCR Launch Campaign",
    "Investment Drive Campaign"
]

ad_sets = [
    "High Budget Audience",
    "Middle Income Buyers",
    "NRI Investors",
    "Retargeting Audience",
    "First Time Buyers"
]

creatives = [
    "Video Ad 1",
    "Carousel Ad 2",
    "Static Image 3",
    "Reel Ad 4",
    "Banner Ad 5"
]

temperatures = ['cold', 'warm', 'hot']
stages = ['new', 'contacted', 'qualified', 'closed']

# =========================
# MAIN
# =========================

print("🚀 Creating 500 leads...")

branches = list(Branch.objects.all())

for i in range(500):

    name = random.choice(names)
    phone = f"9{random.randint(100000000, 999999999)}"
    email = f"{name.replace(' ', '').lower()}{i}@gmail.com"

    source = random.choice(sources)

    campaign = random.choice(campaigns) if source != 'manual' else None
    ad_set = random.choice(ad_sets) if source != 'manual' else None
    creative = random.choice(creatives) if source != 'manual' else None

    Lead.objects.create(
        name=name,
        phone=phone,
        email=email,
        location="Delhi NCR",

        source=source,
        campaign_name=campaign,
        ad_set=ad_set,
        ad_creative=creative,
        landing_page_url="https://example.com" if source != 'manual' else None,

        property_type=random.choice(['flat', 'villa', 'plot']),
        budget_min=random.randint(2000000, 5000000),
        budget_max=random.randint(5000000, 15000000),
        property_location="NCR",
        bhk_preference=random.choice(['1BHK', '2BHK', '3BHK']),
        purpose=random.choice(['buy', 'investment']),
        timeline=random.choice(['immediate', '3_months', '6_months']),
        readiness=random.choice(['hot', 'warm', 'cold']),

        temperature=random.choice(temperatures),
        stage='new',  # 🔥 IMPORTANT: start as new

        branch=random.choice(branches),

        assigned_to=None  # 🔥 UNASSIGNED
    )

    if i % 50 == 0:
        print(f"Created {i} leads...")

print("✅ DONE: 500 leads created")
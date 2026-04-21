from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.
class Attendance(models.Model):
    # Links the record to the specific employee
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    
    # Automatically saves the date the record was created
    date = models.DateField(default=timezone.now)
    
    # Stores the exact times. allowed to be blank until they actually punch out
    punch_in_time = models.DateTimeField(null=True, blank=True)
    punch_out_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.username} - {self.date}"
    
class LocationPing(models.Model):
    # This links directly to Django's built-in User model so we can use the username
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Decimal fields are best for GPS coordinates (gives us accuracy to about 11 centimeters!)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Automatically saves the exact date and time the ping was received
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Orders the database so the newest pings always show up first
        ordering = ['-timestamp']

    def __str__(self):
        # This is what you will see in the Django Admin panel
        return f"{self.employee.username} | {self.timestamp.strftime('%I:%M %p')}"    
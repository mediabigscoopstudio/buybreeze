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
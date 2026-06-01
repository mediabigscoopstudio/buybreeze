import pytz
from django.core.management.base import BaseCommand
from django.utils import timezone

from dash.models import Attendance, UserProfile


class Command(BaseCommand):
    help = 'Mark employees as absent if not punched in'

    def handle(self, *args, **options):
        ist = pytz.timezone('Asia/Kolkata')
        today = timezone.now().astimezone(ist).date()

        employees = UserProfile.objects.filter(
            role='employee',
            status='Enabled',
        ).select_related('branch')

        absent_count = 0
        for emp in employees:
            attendance, created = Attendance.objects.get_or_create(
                employee=emp,
                date=today,
                defaults={
                    'branch': emp.branch,
                    'punch_in': None,
                    'is_absent': True,
                    'status': 'absent',
                },
            )

            if created:
                absent_count += 1
            elif not attendance.punch_in and not attendance.is_absent:
                attendance.is_absent = True
                attendance.status = 'absent'
                attendance.save(update_fields=['is_absent', 'status', 'updated_at'])
                absent_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Marked {absent_count} employees as absent for {today}')
        )

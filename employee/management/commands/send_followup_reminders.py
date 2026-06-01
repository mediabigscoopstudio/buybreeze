from django.core.management.base import BaseCommand
from django.utils import timezone
from dash.models import FollowUp
from dash.notifications import create_notification
import pytz


class Command(BaseCommand):
    help = 'Send follow-up reminders to employees for today\'s scheduled follow-ups'

    def handle(self, *args, **options):
        ist = pytz.timezone('Asia/Kolkata')
        today = timezone.now().astimezone(ist).date()

        followups = FollowUp.objects.filter(
            followup_at__date=today,
            followup_status='pending',
        ).select_related('lead', 'assigned_to', 'assigned_to__user')

        sent = 0
        for followup in followups:
            if followup.assigned_to:
                try:
                    create_notification(
                        from_user=followup.assigned_to.user,
                        to_users=[followup.assigned_to.user],
                        title="🔔 Follow-up Reminder",
                        description=f"You have a follow-up scheduled today for {followup.lead.name}. Notes: {followup.notes or 'No notes'}",
                    )
                    sent += 1
                except Exception as e:
                    self.stderr.write(f"Error for followup {followup.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} follow-up reminders"))

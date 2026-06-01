from dash.models import Notification, NotificationRecipient
from django.contrib.auth.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def initialize_firebase():
    try:
        import firebase_admin
        from firebase_admin import credentials
        from django.conf import settings
        import os
        if not firebase_admin._apps:
            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
        return True
    except Exception as e:
        logger.error(f"Firebase init error: {e}")
        return False


def send_push_notification(user, title, body):
    try:
        initialize_firebase()
        import firebase_admin
        from firebase_admin import messaging
        from dash.models import UserDeviceToken

        try:
            token_obj = UserDeviceToken.objects.get(user=user)
        except UserDeviceToken.DoesNotExist:
            return False

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default'
                )
            ),
            token=token_obj.token
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return False


def create_notification(from_user, to_users, title, description):
    if not to_users:
        return None

    notif = Notification.objects.create(
        from_user=from_user,
        title=title,
        description=description
    )

    for user in to_users:
        NotificationRecipient.objects.get_or_create(
            notification=notif,
            user=user,
            defaults={'is_read': False}
        )
        send_push_notification(user, title, description)

    return notif


def get_user_notifications(user, limit=20):
    return NotificationRecipient.objects.filter(
        user=user
    ).select_related(
        'notification',
        'notification__from_user'
    ).order_by('-notification__created_at')[:limit]


def get_unread_count(user):
    return NotificationRecipient.objects.filter(
        user=user,
        is_read=False
    ).count()


def mark_all_read(user):
    NotificationRecipient.objects.filter(
        user=user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())


def mark_read(user, notification_id):
    NotificationRecipient.objects.filter(
        user=user,
        notification_id=notification_id,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())


def get_managers_for_employee(profile):
    from dash.models import UserProfile
    users = []
    if profile.reports_to:
        users.append(profile.reports_to.user)
        if profile.reports_to.reports_to:
            users.append(profile.reports_to.reports_to.user)
    hr_profiles = UserProfile.objects.filter(
        role='hr',
        branch=profile.branch,
        status='Enabled'
    )
    for hr in hr_profiles:
        users.append(hr.user)
    return list(set(users))


def get_admins():
    return list(User.objects.filter(is_staff=True))

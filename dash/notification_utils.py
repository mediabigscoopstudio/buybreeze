from .models import Notification, NotificationRecipient


def create_notification(from_user, users, title, description):
    """
    from_user = sender
    users = list/queryset of User objects
    """

    notification = Notification.objects.create(
        from_user=from_user,
        title=title,
        description=description
    )

    recipients = []
    for user in users:
        recipients.append(
            NotificationRecipient(
                notification=notification,
                user=user
            )
        )

    NotificationRecipient.objects.bulk_create(recipients)

    return notification
def notifications_context(request):
    if request.user.is_authenticated:
        try:
            from dash.notifications import get_unread_count
            count = get_unread_count(request.user)
        except Exception:
            count = 0
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}

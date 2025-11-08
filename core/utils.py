from django.http import HttpResponseForbidden
from django.utils import timezone
from functools import wraps

from .models import DropFile

def require_subscription(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_subscribed:
            return HttpResponseForbidden("Subscription required")
        return view(request, *args, **kwargs)
    return wrapped


def cleanup_expired_dropfiles():
    expired = DropFile.objects.filter(expires_at__lt=timezone.now())
    for item in expired:
        item.delete()
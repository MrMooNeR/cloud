from django.http import HttpResponseForbidden
from functools import wraps

def require_subscription(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_subscribed:
            return HttpResponseForbidden("Subscription required")
        return view(request, *args, **kwargs)
    return wrapped

try:
    from django.contrib.auth.decorators import login_not_required
except ImportError:  # Django < 5.1 has no LoginRequiredMiddleware to opt out of.

    def login_not_required(view_func):
        return view_func


__all__ = ["login_not_required"]

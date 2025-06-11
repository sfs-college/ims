from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponsePermanentRedirect
from inventory.models import Room
from django.urls import reverse
from django.http import Http404
    

class RedirectLoggedInUsersMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not getattr(request.user, "profile", None):
                raise Http404("User profile not found.")

            if request.user.profile.is_central_admin:
                return HttpResponsePermanentRedirect(reverse('central_admin:dashboard'))
            if request.user.profile.is_incharge:
                rooms = Room.objects.filter(incharge=request.user.profile)
                if not rooms.exists():
                    raise Http404("No rooms assigned to this incharge.")
                # Redirect to the first room's dashboard
                return HttpResponsePermanentRedirect(
                    reverse('room_incharge:room_dashboard', kwargs={'room_slug': rooms.first().slug})
                )

        return super().dispatch(request, *args, **kwargs)
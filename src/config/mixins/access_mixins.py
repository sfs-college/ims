from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponsePermanentRedirect
from inventory.models import Room
from django.urls import reverse
from django.http import Http404
    

class RedirectLoggedInUsersMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)

            # Users without a profile are students (Firebase-auth only, no UserProfile).
            # Let them through to the landing page — they will see the public view.
            if not profile:
                return super().dispatch(request, *args, **kwargs)

            if profile.is_central_admin or profile.is_sub_admin:
                return HttpResponsePermanentRedirect(reverse('central_admin:dashboard'))
            if profile.is_incharge:
                rooms = Room.objects.filter(incharge=profile)
                if not rooms.exists():
                    raise Http404("No rooms assigned to this incharge.")
                # Redirect to the first room's dashboard
                return HttpResponsePermanentRedirect(
                    reverse('room_incharge:room_dashboard', kwargs={'room_slug': rooms.first().slug})
                )

            # Students and any other role — let them see the landing page
            return super().dispatch(request, *args, **kwargs)

        return super().dispatch(request, *args, **kwargs)
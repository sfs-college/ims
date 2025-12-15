from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from inventory.models import Issue

@csrf_exempt
def run_escalation(request):
    token = request.headers.get("X-CRON-TOKEN")

    if token != settings.CRON_SECRET:
        return HttpResponseForbidden("Invalid cron token")

    now = timezone.now()
    expired = Issue.objects.filter(
        resolved=False,
        tat_deadline__lt=now
    )

    escalated_count = 0
    for issue in expired:
        result = issue.escalate(notify=True)
        if result.get("escalated"):
            escalated_count += 1

    return JsonResponse({
        "status": "ok",
        "checked": expired.count(),
        "escalated": escalated_count,
        "timestamp": now
    })

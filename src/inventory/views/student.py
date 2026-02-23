# ims/src/inventory/views/student.py
from django.shortcuts import render, redirect
from django.views import View
from inventory.forms.student import IssueReportForm
from inventory.models import Organisation, Issue, Room
from config.api.student_data import fetch_student_data
from django.conf import settings
from inventory.email import safe_send_mail
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages


class StudentPortalLoginView(View):
    """
    Entry point for students: shows the Google Auth UI.
    If already logged in, redirects straight to the reporting form.
    """
    template_name = 'student/portal_login.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('student:report_issue')
        return render(request, self.template_name)


class IssueReportView(View):
    """
    Student Issue Reporting + Tracking.
    """
    template_name = 'student/issue_report.html'
    form_class = IssueReportForm
    login_url = 'student:portal_login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(self.login_url)
        return super().dispatch(request, *args, **kwargs)

    def _get_email(self) -> str:
        """
        Resolve the authenticated student's email. Uses three fallback
        sources so it works regardless of how the User was created.
        """
        user = self.request.user
        if not user.is_authenticated:
            return ""

        # Source 1: user.email (set by firebase_login_callback)
        if user.email:
            return user.email.strip().lower()

        # Source 2: allauth SocialAccount extra_data (if allauth is also in play)
        try:
            from allauth.socialaccount.models import SocialAccount
            sa = SocialAccount.objects.filter(user=user).first()
            if sa:
                email = (
                    sa.extra_data.get("email") or
                    sa.extra_data.get("emailAddress") or ""
                ).strip().lower()
                if email:
                    user.email = email
                    user.save(update_fields=["email"])
                    return email
        except Exception:
            pass

        # Source 3: username field equals email (fallback for older records)
        uname = getattr(user, 'username', '') or ''
        if '@' in uname:
            return uname.strip().lower()

        return ""

    def _get_student_data(self, email: str):
        if not email:
            return None
        api_key    = getattr(settings, "STUDENT_API_KEY", None)
        api_secret = getattr(settings, "STUDENT_API_SECRET_KEY", None)  # matches settings.py key name
        if not api_key or not api_secret:
            return None
        try:
            response = fetch_student_data(email, api_key, api_secret)
            return response if isinstance(response, dict) else None
        except Exception:
            return None

    def get(self, request, *args, **kwargs):
        email = self._get_email()
        form  = self.form_class()

        selected_category = request.GET.get('category')
        if selected_category:
            form.fields['room'].queryset = Room.objects.filter(
                room_category=selected_category
            )

        ticket       = None
        tickets      = None
        search_email = request.GET.get("email", "").strip()

        if request.GET.get("ticket_id"):
            try:
                ticket = Issue.objects.get(ticket_id=request.GET["ticket_id"])
            except Issue.DoesNotExist:
                pass

        if search_email:
            tickets = Issue.objects.filter(
                reporter_email__iexact=search_email
            ).order_by("-created_on")

        return render(request, self.template_name, {
            "form":              form,
            "ticket":            ticket,
            "tickets":           tickets,
            "categories":        Room.ROOM_CATEGORIES,
            "selected_category": selected_category,
            "user":              request.user,
            "student_email":     email,
        })

    def post(self, request, *args, **kwargs):
        # Always derive email from the verified session — never trust POST data alone
        email = self._get_email()

        if not email:
            messages.error(
                request,
                "Your session email could not be verified. Please log out and sign in again."
            )
            return redirect(self.login_url)

        form = self.form_class(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form":          form,
                "categories":    Room.ROOM_CATEGORIES,
                "student_email": email,
            })

        subject     = form.cleaned_data["subject"]
        description = form.cleaned_data["description"]
        room        = form.cleaned_data["room"]

        # Optional external student API lookup
        student_data = self._get_student_data(email)
        student = None
        if student_data and student_data.get("success"):
            for s in student_data.get("data", []):
                if (s.get("email") or "").lower() == email:
                    student = s
                    break

        created_by   = student["name"] if student else email
        organisation = Organisation.objects.first()

        issue = Issue(
            organisation   = organisation,
            room           = room,
            created_by     = created_by,
            reporter_email = email,          # always the verified session email
            subject        = subject,
            description    = description,
        )

        if room.incharge:
            issue.assigned_to      = room.incharge
            issue.status           = "open"
            issue.escalation_level = 0

        hours = int(getattr(settings, "DEFAULT_TAT_HOURS", 48))
        issue.tat_deadline = timezone.now() + timedelta(hours=hours)
        issue.save()

        # Notify room incharge
        if (
            issue.assigned_to
            and getattr(issue.assigned_to, "user", None)
            and issue.assigned_to.user.email
        ):
            try:
                safe_send_mail(
                    subject=f"[Blixtro] New Ticket {issue.ticket_id}: {issue.subject}",
                    message=(
                        f"You have been assigned a new ticket.\n\n"
                        f"Ticket ID   : {issue.ticket_id}\n"
                        f"Reported by : {email}\n"
                        f"Description : {issue.description}\n"
                        f"TAT         : {issue.tat_deadline}\n"
                    ),
                    recipient_list=[issue.assigned_to.user.email],
                )
            except Exception as e:
                print(f"[student_view] incharge email error: {e}", flush=True)

        # Confirm to student
        try:
            safe_send_mail(
                subject=f"[Blixtro] Ticket Received: {issue.ticket_id}",
                message=(
                    f"Your ticket has been created.\n\n"
                    f"Ticket ID : {issue.ticket_id}\n"
                    f"Status    : {issue.status}\n"
                    f"TAT       : {issue.tat_deadline}\n"
                ),
                from_email=None,
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception:
            pass

        return redirect("student:issue_report_success")


class TicketStatusView(View):
    template_name = 'student/ticket_status.html'

    def get(self, request, *args, **kwargs):
        ticket  = None
        tickets = None

        ticket_id    = request.GET.get("ticket_id")
        search_email = request.GET.get("email", "").strip()

        if ticket_id:
            try:
                ticket = Issue.objects.get(ticket_id=ticket_id)
            except Issue.DoesNotExist:
                pass

        if search_email:
            tickets = Issue.objects.filter(
                reporter_email__iexact=search_email
            ).order_by("-created_on")

        return render(request, self.template_name, {
            "ticket":  ticket,
            "tickets": tickets,
        })
# ims/src/inventory/views/student.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from inventory.forms.student import IssueReportForm
from inventory.models import Organisation, Issue, Room, UserProfile
from config.api.student_data import fetch_student_data
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib import messages

class IssueReportView(View):
    """
    Student Issue Reporting + Tracking
    """
    template_name = 'student/issue_report.html'
    form_class = IssueReportForm

    def get_student_data(self):
        """
        Safely fetch student data from external API.
        Returns:
            dict { "success": bool, "data": [...] } or None
        """

        email = self.request.POST.get("email")
        if not email:
            return None

        # Get API credentials from settings
        API_KEY = getattr(settings, "STUDENT_API_KEY", None)
        API_SECRET_KEY = getattr(settings, "STUDENT_API_SECRET", None)

        # If no API keys → silently disable API, do not print anything
        if not API_KEY or not API_SECRET_KEY:
            return None

        try:
            # Call external API correctly
            response = fetch_student_data(email, API_KEY, API_SECRET_KEY)

            if isinstance(response, dict):
                return response

            return None

        except:
            # Do NOT print — silent fail
            return None



    def get(self, request, *args, **kwargs):
        form = self.form_class()

        ticket = None
        tickets = None

        ticket_id = request.GET.get("ticket_id")
        email = request.GET.get("email")

        if ticket_id:
            try:
                ticket = Issue.objects.get(ticket_id=ticket_id)
            except Issue.DoesNotExist:
                ticket = None

        if email:
            tickets = Issue.objects.filter(
                reporter_email__iexact=email
            ).order_by("-created_on")

        return render(request, self.template_name, {
            "form": form,
            "ticket": ticket,
            "tickets": tickets
        })

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            subject = form.cleaned_data["subject"]
            description = form.cleaned_data["description"]
            room = form.cleaned_data["room"]

            # Student verification via API (optional)
            student_data = self.get_student_data()
            student = None

            if student_data and student_data.get("success"):
                for s in student_data.get("data", []):
                    if s.get("email") == email:
                        student = s
                        break

            created_by = student["name"] if student else email

            organisation = Organisation.objects.first()

            issue = Issue(
                organisation=organisation,
                room=room,
                created_by=created_by,
                reporter_email=email,
                subject=subject,
                description=description
            )

            # Assign to room incharge
            if room.incharge:
                issue.assigned_to = room.incharge
                issue.status = "open"
                issue.escalation_level = 0

            # TAT assignment (TEST MODE set to 1 minute)
            hours = int(getattr(settings, "DEFAULT_TAT_HOURS", 48))
            issue.tat_deadline = timezone.now() + timedelta(hours=hours)

            issue.save()

            # SEND EMAILS (unchanged)
            if issue.assigned_to and issue.assigned_to.user.email:
                try:
                    send_mail(
                        f"[Blixtro] New Ticket {issue.ticket_id}: {issue.subject}",
                        f"You have been assigned a new ticket.\n\n"
                        f"Ticket ID: {issue.ticket_id}\n"
                        f"Description: {issue.description}\n"
                        f"TAT: {issue.tat_deadline}\n",
                        settings.DEFAULT_FROM_EMAIL,
                        [issue.assigned_to.user.email]
                    )
                except Exception as e:
                    print("Mail error:", e)

            try:
                send_mail(
                    f"[Blixtro] Ticket Received: {issue.ticket_id}",
                    f"Your ticket has been created.\n\n"
                    f"Ticket ID: {issue.ticket_id}\n"
                    f"Status: {issue.status}\n"
                    f"TAT: {issue.tat_deadline}\n",
                    settings.DEFAULT_FROM_EMAIL,
                    [email]
                )
            except:
                pass

            return redirect("student:issue_report_success")

        return render(request, self.template_name, {"form": form})



class TicketStatusView(View):
    template_name = 'student/ticket_status.html'

    def get(self, request, *args, **kwargs):
        ticket_id = request.GET.get("ticket_id")
        email = request.GET.get("email")

        ticket = None
        tickets = None

        if ticket_id:
            try:
                ticket = Issue.objects.get(ticket_id=ticket_id)
            except Issue.DoesNotExist:
                pass

        if email:
            tickets = Issue.objects.filter(
                reporter_email__iexact=email
            ).order_by("-created_on")

        return render(request, self.template_name, {
            "ticket": ticket,
            "tickets": tickets
        })

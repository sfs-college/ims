from django.urls import path
from inventory.views.student import IssueReportView, TicketStatusView, StudentPortalLoginView
from django.views.generic import TemplateView

app_name = 'student'

urlpatterns = [
    path('report_issue/', IssueReportView.as_view(), name='report_issue'),
    path('issue_report_success/', TemplateView.as_view(template_name='student/issue_report_success.html'), name='issue_report_success'),
    path('track_ticket/', TicketStatusView.as_view(), name='track_ticket'),
    path('portal/', StudentPortalLoginView.as_view(), name='portal_login')
]

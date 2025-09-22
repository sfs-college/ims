from django.shortcuts import render, redirect
from django.views import View
from inventory.forms.student import IssueReportForm
from inventory.models import Organisation, Issue, Room
from config.api.student_data import fetch_student_data
from django.conf import settings

class IssueReportView(View):
    template_name = 'student/issue_report.html'
    form_class = IssueReportForm

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            reg_no = form.cleaned_data['reg_no']
            admission_no = form.cleaned_data['admission_no']
            student_data = self.get_student_data()
            student = self.verify_student(student_data, reg_no, admission_no)
            if student:
                issue_report = form.save(commit=False)
                issue_report.created_by = student['studentName']
                issue_report.organisation = issue_report.room.organisation 
                issue_report.save()
                return redirect('student:issue_report_success')
            else:
                form.add_error(None, 'Student not found.')
        return render(request, self.template_name, {'form': form})

    def get_student_data(self):
        college_code = settings.COLLEGE_CODE
        STUDENT_API_KEY = settings.STUDENT_API_KEY
        STUDENT_API_SECRET_KEY = settings.STUDENT_API_SECRET_KEY
        return fetch_student_data(college_code, STUDENT_API_KEY, STUDENT_API_SECRET_KEY)

    def verify_student(self, student_data, reg_no, admission_no):
        if student_data and student_data['success']:
            for student in student_data['data']:
                if (reg_no and student['regNo'] == reg_no) or (admission_no and student['admissionNo'] == admission_no):
                    return student
        return None

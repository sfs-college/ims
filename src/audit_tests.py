"""
Audit test suite for the Blixtro IMS Django project.
Run with: python manage.py test audit_tests --settings=config.test_settings
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_user(email="test@sfscollege.in", password="testpass123"):
    user = User.objects.create_user(email=email, password=password)
    user.is_active = True
    user.save()
    return user


def make_org():
    from core.models import Organisation
    return Organisation.objects.create(name="Test Org")


def make_profile(user, org, is_central_admin=False, is_sub_admin=False, is_incharge=False):
    from core.models import UserProfile
    return UserProfile.objects.create(
        user=user,
        org=org,
        first_name="Test",
        last_name="User",
        is_central_admin=is_central_admin,
        is_sub_admin=is_sub_admin,
        is_incharge=is_incharge,
    )


def make_room(org, incharge=None):
    from inventory.models import Room, Department
    dept, _ = Department.objects.get_or_create(
        organisation=org, department_name="Test Dept",
        defaults={}
    )
    return Room.objects.create(
        organisation=org,
        room_name="Test Room",
        label="TR-01",
        department=dept,
        incharge=incharge,
        room_category="classrooms",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. SYNTAX CHECK (already done via AST — this just confirms import works)
# ─────────────────────────────────────────────────────────────────────────────

class SyntaxCheckTest(TestCase):
    def test_all_modules_importable(self):
        """Verify key modules can be imported without errors."""
        import core.views
        import core.models
        import inventory.views.aura
        import inventory.views.room_incharge
        import inventory.views.central_admin
        import inventory.views.student
        import config.settings
        import config.urls
        self.assertTrue(True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIREBASE LOGIN CALLBACK TESTS
# ─────────────────────────────────────────────────────────────────────────────

class FirebaseLoginCallbackTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.url = "/core/firebase-login/"

    def _post(self, data):
        from core.views import firebase_login_callback
        request = self.factory.post("/core/firebase-login/", data)
        # Attach session middleware manually
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()
        from django.contrib.messages.storage.fallback import FallbackStorage
        request._messages = FallbackStorage(request)
        return firebase_login_callback(request)

    def test_get_request_redirects_to_login(self):
        """GET request should redirect to student portal login."""
        from core.views import firebase_login_callback
        request = self.factory.get("/core/firebase-login/")
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()
        response = firebase_login_callback(request)
        self.assertEqual(response.status_code, 302)

    def test_missing_token_redirects(self):
        """POST with no id_token should redirect back."""
        response = self._post({"id_token": ""})
        self.assertEqual(response.status_code, 302)

    @patch("core.views.auth.verify_id_token")
    def test_invalid_token_redirects(self, mock_verify):
        """Invalid Firebase token should redirect back."""
        mock_verify.side_effect = Exception("Invalid token")
        response = self._post({"id_token": "bad_token"})
        self.assertEqual(response.status_code, 302)

    @patch("core.views.auth.verify_id_token")
    def test_wrong_domain_redirects(self, mock_verify):
        """Token from wrong email domain should be rejected."""
        mock_verify.return_value = {
            "email": "student@gmail.com",
            "name": "Outside User",
        }
        response = self._post({"id_token": "valid_token"})
        self.assertEqual(response.status_code, 302)

    @patch("core.views.auth.verify_id_token")
    def test_valid_token_correct_domain_logs_in(self, mock_verify):
        """Valid token with correct domain should create/login user."""
        mock_verify.return_value = {
            "email": "student@sfscollege.in",
            "name": "Test Student",
        }
        response = self._post({"id_token": "valid_token"})
        # Should redirect (to report_issue or capacitor callback)
        self.assertEqual(response.status_code, 302)
        # User should now exist
        self.assertTrue(User.objects.filter(email="student@sfscollege.in").exists())

    @patch("core.views.auth.verify_id_token")
    def test_valid_token_existing_user(self, mock_verify):
        """Valid token for existing user should log them in without creating duplicate."""
        User.objects.create_user(email="existing@sfscollege.in", password="x")
        mock_verify.return_value = {
            "email": "existing@sfscollege.in",
            "name": "Existing User",
        }
        response = self._post({"id_token": "valid_token"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.filter(email="existing@sfscollege.in").count(), 1)

    @patch("core.views.auth.verify_id_token")
    def test_token_with_no_email_redirects(self, mock_verify):
        """Token payload missing email should redirect."""
        mock_verify.return_value = {"name": "No Email User"}
        response = self._post({"id_token": "valid_token"})
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────────────────────────────────────
# 3. MASTER INVENTORY ACCESS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class MasterInventoryAccessTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = make_org()

        # Central admin
        self.admin_user = make_user("admin@sfscollege.in")
        self.admin_profile = make_profile(self.admin_user, self.org, is_central_admin=True)

        # Room incharge
        self.incharge_user = make_user("incharge@sfscollege.in")
        self.incharge_profile = make_profile(self.incharge_user, self.org, is_incharge=True)

    def _make_request(self, user, body):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.post(
            "/central_admin/master-inventory/access/grant/",
            data=json.dumps(body),
            content_type="application/json",
        )
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_grant_access_unauthorized_user(self):
        """Non-admin user should get 403."""
        from inventory.views.aura import master_inventory_grant_access
        non_admin = make_user("nobody@sfscollege.in")
        make_profile(non_admin, self.org)
        request = self._make_request(non_admin, {"incharge_slug": self.incharge_profile.slug, "access_type": "view"})
        response = master_inventory_grant_access(request)
        self.assertEqual(response.status_code, 403)

    def test_grant_view_access(self):
        """Admin should be able to grant view access."""
        from inventory.views.aura import master_inventory_grant_access
        request = self._make_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "access_type": "view"}
        )
        response = master_inventory_grant_access(request)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["can_view"])
        self.assertFalse(data["can_edit"])

    def test_grant_edit_access(self):
        """Admin should be able to grant edit access."""
        from inventory.views.aura import master_inventory_grant_access
        request = self._make_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "access_type": "edit"}
        )
        response = master_inventory_grant_access(request)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["can_view"])
        self.assertTrue(data["can_edit"])

    def test_grant_invalid_access_type(self):
        """Invalid access_type should return 400."""
        from inventory.views.aura import master_inventory_grant_access
        request = self._make_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "access_type": "superuser"}
        )
        response = master_inventory_grant_access(request)
        self.assertEqual(response.status_code, 400)

    def test_grant_missing_slug(self):
        """Missing incharge_slug should return 400."""
        from inventory.views.aura import master_inventory_grant_access
        request = self._make_request(self.admin_user, {"access_type": "view"})
        response = master_inventory_grant_access(request)
        self.assertEqual(response.status_code, 400)

    def _make_revoke_request(self, user, body):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.post(
            "/central_admin/master-inventory/access/revoke/",
            data=json.dumps(body),
            content_type="application/json",
        )
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_revoke_access_unauthorized(self):
        """Non-admin should get 403 on revoke."""
        from inventory.views.aura import master_inventory_revoke_access
        non_admin = make_user("nobody2@sfscollege.in")
        make_profile(non_admin, self.org)
        request = self._make_revoke_request(non_admin, {"incharge_slug": self.incharge_profile.slug})
        response = master_inventory_revoke_access(request)
        self.assertEqual(response.status_code, 403)

    def test_revoke_all_access(self):
        """Admin should be able to revoke all access."""
        from inventory.views.aura import master_inventory_grant_access, master_inventory_revoke_access
        from inventory.models import MasterInventoryAccess

        # First grant
        grant_req = self._make_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "access_type": "view"}
        )
        master_inventory_grant_access(grant_req)
        self.assertTrue(MasterInventoryAccess.objects.filter(incharge=self.incharge_profile).exists())

        # Then revoke
        revoke_req = self._make_revoke_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "revoke_type": "all"}
        )
        response = master_inventory_revoke_access(revoke_req)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "success")
        self.assertFalse(MasterInventoryAccess.objects.filter(incharge=self.incharge_profile).exists())

    def test_revoke_edit_only(self):
        """Revoking edit should keep view access."""
        from inventory.views.aura import master_inventory_grant_access, master_inventory_revoke_access
        from inventory.models import MasterInventoryAccess

        # Grant edit
        grant_req = self._make_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "access_type": "edit"}
        )
        master_inventory_grant_access(grant_req)

        # Revoke edit only
        revoke_req = self._make_revoke_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "revoke_type": "edit"}
        )
        response = master_inventory_revoke_access(revoke_req)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "success")

        access = MasterInventoryAccess.objects.get(incharge=self.incharge_profile)
        self.assertTrue(access.can_view)
        self.assertFalse(access.can_edit)

    def test_revoke_nonexistent_access_returns_success(self):
        """Revoking access that doesn't exist should still return success."""
        from inventory.views.aura import master_inventory_revoke_access
        request = self._make_revoke_request(
            self.admin_user,
            {"incharge_slug": self.incharge_profile.slug, "revoke_type": "all"}
        )
        response = master_inventory_revoke_access(request)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "success")


# ─────────────────────────────────────────────────────────────────────────────
# 4. ROOM REPORT VIEW TESTS
# ─────────────────────────────────────────────────────────────────────────────

class RoomReportViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = make_org()
        self.incharge_user = make_user("incharge2@sfscollege.in")
        self.incharge_profile = make_profile(self.incharge_user, self.org, is_incharge=True)
        self.room = make_room(self.org, incharge=self.incharge_profile)

    def _make_get_request(self, user, room_slug, fmt="excel"):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.factory.get(
            f"/room_incharge/rooms/{room_slug}/report/",
            {"format": fmt}
        )
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_excel_report_returns_200(self):
        """Excel format should return 200 with correct content type."""
        from inventory.views.room_incharge import RoomReportView
        request = self._make_get_request(self.incharge_user, self.room.slug, fmt="excel")
        view = RoomReportView.as_view()
        response = view(request, room_slug=self.room.slug)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "spreadsheetml",
            response.get("Content-Type", ""),
        )

    def test_excel_report_has_content_disposition(self):
        """Excel response should have Content-Disposition attachment header."""
        from inventory.views.room_incharge import RoomReportView
        request = self._make_get_request(self.incharge_user, self.room.slug, fmt="excel")
        view = RoomReportView.as_view()
        response = view(request, room_slug=self.room.slug)
        self.assertIn("attachment", response.get("Content-Disposition", ""))
        self.assertIn(".xlsx", response.get("Content-Disposition", ""))

    def test_unauthenticated_redirects(self):
        """Unauthenticated request should redirect to login."""
        from django.contrib.auth.models import AnonymousUser
        from inventory.views.room_incharge import RoomReportView
        from django.contrib.sessions.backends.db import SessionStore
        request = self.factory.get(f"/room_incharge/rooms/{self.room.slug}/report/", {"format": "excel"})
        request.user = AnonymousUser()
        request.session = SessionStore()
        view = RoomReportView.as_view()
        response = view(request, room_slug=self.room.slug)
        self.assertEqual(response.status_code, 302)

    def test_invalid_room_slug_returns_404(self):
        """Non-existent room slug should return 404."""
        from inventory.views.room_incharge import RoomReportView
        request = self._make_get_request(self.incharge_user, "nonexistent-room", fmt="excel")
        view = RoomReportView.as_view()
        from django.http import Http404
        with self.assertRaises(Http404):
            view(request, room_slug="nonexistent-room")


# ─────────────────────────────────────────────────────────────────────────────
# 5. URL ROUTING TESTS
# ─────────────────────────────────────────────────────────────────────────────

class URLRoutingTest(TestCase):
    def test_landing_page_resolves(self):
        match = resolve("/")
        self.assertEqual(match.url_name, "landing_page")

    def test_core_login_resolves(self):
        match = resolve("/core/login/")
        self.assertEqual(match.url_name, "login")

    def test_core_firebase_login_resolves(self):
        match = resolve("/core/firebase-login/")
        self.assertEqual(match.url_name, "firebase_login")

    def test_student_report_issue_resolves(self):
        match = resolve("/students/report_issue/")
        self.assertEqual(match.url_name, "report_issue")

    def test_student_track_ticket_resolves(self):
        match = resolve("/students/track_ticket/")
        self.assertEqual(match.url_name, "track_ticket")

    def test_central_admin_dashboard_resolves(self):
        match = resolve("/central_admin/")
        self.assertEqual(match.url_name, "dashboard")

    def test_aura_dashboard_resolves(self):
        match = resolve("/central_admin/aura/")
        self.assertEqual(match.url_name, "aura_dashboard")

    def test_master_inventory_grant_resolves(self):
        match = resolve("/central_admin/master-inventory/access/grant/")
        self.assertEqual(match.url_name, "master_inventory_grant_access")

    def test_master_inventory_revoke_resolves(self):
        match = resolve("/central_admin/master-inventory/access/revoke/")
        self.assertEqual(match.url_name, "master_inventory_revoke_access")

    def test_room_report_resolves(self):
        match = resolve("/room_incharge/rooms/test-room/report/")
        self.assertEqual(match.url_name, "room_report")

    def test_escalation_resolves(self):
        match = resolve("/internal/escalate/")
        self.assertEqual(match.url_name, "run_escalation")


# ─────────────────────────────────────────────────────────────────────────────
# 6. SECURITY TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SecurityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = make_org()

    def test_central_admin_dashboard_requires_login(self):
        """Central admin dashboard should redirect unauthenticated users."""
        response = self.client.get("/central_admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/core/login", response["Location"])

    def test_aura_dashboard_requires_login(self):
        """Aura dashboard should redirect unauthenticated users."""
        response = self.client.get("/central_admin/aura/")
        self.assertEqual(response.status_code, 302)

    def test_aura_api_data_requires_auth(self):
        """Aura data manager API should return 403 for unauthenticated."""
        response = self.client.get("/central_admin/aura/api/data-manager/?model=issues")
        # Either 302 (redirect to login) or 403 is acceptable
        self.assertIn(response.status_code, [302, 403])

    def test_master_inventory_grant_requires_post(self):
        """Grant access endpoint should only accept POST (require_POST decorator)."""
        response = self.client.get("/central_admin/master-inventory/access/grant/")
        self.assertEqual(response.status_code, 405)

    def test_master_inventory_revoke_requires_post(self):
        """Revoke access endpoint should only accept POST."""
        response = self.client.get("/central_admin/master-inventory/access/revoke/")
        self.assertEqual(response.status_code, 405)

    def test_escalation_endpoint_requires_token(self):
        """Escalation endpoint without token should return 403."""
        response = self.client.post("/internal/escalate/")
        self.assertEqual(response.status_code, 403)

    def test_escalation_endpoint_with_wrong_token(self):
        """Escalation endpoint with wrong token should return 403."""
        response = self.client.post(
            "/internal/escalate/",
            HTTP_X_CRON_TOKEN="wrong-token"
        )
        self.assertEqual(response.status_code, 403)

    def test_student_report_issue_requires_login(self):
        """Issue report view should redirect unauthenticated users."""
        response = self.client.get("/students/report_issue/")
        self.assertEqual(response.status_code, 302)

    def test_room_incharge_views_require_login(self):
        """Room incharge views should redirect unauthenticated users."""
        response = self.client.get("/room_incharge/rooms/test-room/report/")
        self.assertEqual(response.status_code, 302)

    def test_aura_delete_unauthenticated_returns_403(self):
        """aura_delete_record should return 403 for unauthenticated POST (not crash with AttributeError)."""
        # This tests the BUG FIX: original code did request.user.profile which crashes on AnonymousUser
        from inventory.views.aura import aura_delete_record
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        factory = RequestFactory()
        request = factory.post(
            "/central_admin/aura/api/delete/",
            data=json.dumps({"model": "issues", "id": 1}),
            content_type="application/json",
        )
        request.user = AnonymousUser()
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        # Should return 403, not raise AttributeError
        response = aura_delete_record(request)
        self.assertEqual(response.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 7. LOGIC / BUG TESTS
# ─────────────────────────────────────────────────────────────────────────────

class LogicBugTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.admin_user = make_user("admin2@sfscollege.in")
        self.admin_profile = make_profile(self.admin_user, self.org, is_central_admin=True)

    def test_aura_delete_record_with_invalid_model_returns_400(self):
        """aura_delete_record with invalid model should return 400, not crash with ValueError."""
        from inventory.views.aura import aura_delete_record
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage
        factory = RequestFactory()
        request = factory.post(
            "/central_admin/aura/api/delete/",
            data=json.dumps({"model": "nonexistent", "id": 1}),
            content_type="application/json",
        )
        request.user = self.admin_user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        # Should not raise ValueError — should return 400 for invalid model
        response = aura_delete_record(request)
        self.assertEqual(response.status_code, 400)

    def test_master_inventory_grant_idempotent(self):
        """Granting access twice should not create duplicate records."""
        from inventory.views.aura import master_inventory_grant_access
        from inventory.models import MasterInventoryAccess
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage

        incharge_user = make_user("incharge3@sfscollege.in")
        incharge_profile = make_profile(incharge_user, self.org, is_incharge=True)

        factory = RequestFactory()
        for _ in range(2):
            request = factory.post(
                "/central_admin/master-inventory/access/grant/",
                data=json.dumps({"incharge_slug": incharge_profile.slug, "access_type": "view"}),
                content_type="application/json",
            )
            request.user = self.admin_user
            request.session = SessionStore()
            request._messages = FallbackStorage(request)
            master_inventory_grant_access(request)

        count = MasterInventoryAccess.objects.filter(incharge=incharge_profile).count()
        self.assertEqual(count, 1, "Duplicate access records should not be created")

    def test_firebase_login_creates_user_only_once(self):
        """Calling firebase_login_callback twice with same email should not duplicate user."""
        from core.views import firebase_login_callback
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.messages.storage.fallback import FallbackStorage

        factory = RequestFactory()
        with patch("core.views.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {"email": "dup@sfscollege.in", "name": "Dup User"}
            for _ in range(2):
                request = factory.post("/core/firebase-login/", {"id_token": "tok"})
                request.session = SessionStore()
                request._messages = FallbackStorage(request)
                firebase_login_callback(request)

        self.assertEqual(User.objects.filter(email="dup@sfscollege.in").count(), 1)

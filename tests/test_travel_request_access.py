import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
except ModuleNotFoundError as import_error:  # pragma: no cover - local minimal test environments
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TravelRequestAccessTests(unittest.TestCase):
    def setUp(self):
        self.request = SimpleNamespace(user_id=10)

    def user(self, user_id):
        return SimpleNamespace(id=user_id, is_authenticated=True)

    def test_requester_can_access_request(self):
        with patch.object(app_module, 'current_user', self.user(10)), \
             patch.object(app_module, 'is_current_user_travel_request_participant', return_value=False):
            self.assertTrue(app_module.can_user_access_travel_request(self.request))

    def test_unrelated_admin_cannot_access_request(self):
        with patch.object(app_module, 'current_user', self.user(99)), \
             patch.object(app_module, 'is_current_user_travel_request_participant', return_value=False), \
             patch.object(app_module, 'is_admin_authorized', return_value=True), \
             patch.object(app_module, 'is_approval_center_user', return_value=True):
            self.assertFalse(app_module.can_user_access_travel_request(self.request))

    def test_participant_can_access_request(self):
        with patch.object(app_module, 'current_user', self.user(99)), \
             patch.object(app_module, 'is_current_user_travel_request_participant', return_value=True):
            self.assertTrue(app_module.can_user_access_travel_request(self.request))

    def test_only_assigned_approver_can_review_request(self):
        approver = self.user(20)
        with patch.object(app_module, 'is_configured_approver_user', return_value=True), \
             patch.object(app_module, 'can_user_approve_for_requester', return_value=True):
            self.assertTrue(app_module.can_user_review_travel_request(approver, self.request))

        with patch.object(app_module, 'is_configured_approver_user', return_value=True), \
             patch.object(app_module, 'can_user_approve_for_requester', return_value=False):
            self.assertFalse(app_module.can_user_review_travel_request(approver, self.request))

    def test_approver_attachment_access_does_not_grant_requester_access(self):
        approver = self.user(20)
        with patch.object(app_module, 'current_user', approver), \
             patch.object(app_module, 'can_user_access_travel_request', return_value=False), \
             patch.object(app_module, 'can_user_review_travel_request', return_value=True):
            self.assertTrue(app_module.can_current_user_access_travel_request_attachment(self.request))

        with patch.object(app_module, 'current_user', self.user(99)), \
             patch.object(app_module, 'can_user_access_travel_request', return_value=False), \
             patch.object(app_module, 'can_user_review_travel_request', return_value=False):
            self.assertFalse(app_module.can_current_user_access_travel_request_attachment(self.request))


if __name__ == '__main__':
    unittest.main()

import unittest

from fastapi import HTTPException

from backend.app.services.auth_policy import (
    assert_password_change_complete,
    requires_password_change,
)


class AuthPolicyTests(unittest.TestCase):
    def test_server_owned_flag_requires_password_change(self):
        user = {"app_metadata": {"must_change_password": True}}
        self.assertTrue(requires_password_change(user))

    def test_server_owned_false_overrides_legacy_user_flag(self):
        user = {
            "app_metadata": {"must_change_password": False},
            "user_metadata": {"must_change_password": True},
        }
        self.assertFalse(requires_password_change(user))

    def test_legacy_flag_remains_supported_during_migration(self):
        user = {"user_metadata": {"must_change_password": "true"}}
        self.assertTrue(requires_password_change(user))

    def test_missing_flag_does_not_require_password_change(self):
        self.assertFalse(requires_password_change({}))

    def test_pending_password_change_is_blocked_by_backend(self):
        with self.assertRaises(HTTPException) as caught:
            assert_password_change_complete(
                {"app_metadata": {"must_change_password": True}},
            )
        self.assertEqual(caught.exception.status_code, 403)

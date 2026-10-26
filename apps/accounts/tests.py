from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_create_user_with_phone(self):
        user = get_user_model().objects.create_user(
            username="khach1", password="Matkhau-manh-123", phone="0900000000"
        )
        self.assertEqual(user.phone, "0900000000")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("Matkhau-manh-123"))

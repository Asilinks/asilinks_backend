
from rest_framework.test import APISimpleTestCase
from rest_framework.reverse import reverse
from rest_framework import status

from .documents import Client, Partner
from requesting.documents import Request
from authentication.documents import Account

# Create your tests here.

class ProfileConsistencyTests(APISimpleTestCase):

    def test_partner_profile(self):
        """
        Ensure partner profile are consistence.
        """

        for account in Account.objects.all():
            with self.subTest(account=account):
                if(account.has_partner_profile()):
                    self.assertIsInstance(account.partner_profile, Partner)

    def test_client_profile(self):
        """
        Ensure client profile are consistence.
        """

        for account in Account.objects.all():
            with self.subTest(account=account):
                self.assertIsInstance(account.client_profile, Client)

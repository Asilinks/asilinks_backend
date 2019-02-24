
from rest_framework.test import APISimpleTestCase
from rest_framework.reverse import reverse
from rest_framework import status

from authentication.documents import Account, Location
from fcm.documents import FCMDevice

# Create your tests here.

class NotAuthenticatedTests(APISimpleTestCase):

    def test_create_account(self):
        """
        Ensure user can create account.
        """
        url = reverse('account-list', kwargs={'version':'dev'})

        data =  {
            "email": "testing@asilinks.com",
            "refer_email": "not_registered@asilinks.com",
            "first_name": "Felicia",
            "last_name": "Lopez",
            "birth_date": "1990-01-01",
            "password": "supercontraseña",
            "residence": "5b3a51a85e2bab0507bbc560",
            "commercial_sector": "textil",
            "gender": "F"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data['refer_email'] = 'user2@asilinks.com'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        account = Account.objects.get(email=data['email'])
        self.assertIsNotNone(account.client_profile)
        self.assertIsNone(account.partner_profile)

        # limpiando...
        account.client_profile.delete()
        account.delete()

    def test_create_account_plus_partner(self):
        """
        Ensure user can create account with partner profile.
        """
        url = reverse('account-plus-partner', kwargs={'version':'dev'})

        data =  {
            "email": "testing@asilinks.com",
            "refer_email": "user2@asilinks.com",
            "first_name": "Felicia",
            "last_name": "Lopez",
            "birth_date": "1990-01-01",
            "password": "supercontraseña",
            "residence": "5b3a51a85e2bab0507bbc560",
            "commercial_sector": "textil",
            "gender": "F",
        }

        from main.documents import Test
        correct = [{'test': str(test.id),
            'positive_answer': test.positive_answer,
            'negative_answer': test.negative_answer,
        } for test in Test.objects.filter(group_test='BASE')]
        # self.assertEqual(correct, status.HTTP_201_CREATED)

        random = [{'test': str(test.id),
            'positive_answer': 1,
            'negative_answer': 2,
        } for test in Test.objects.filter(group_test='BASE')]

        another = [{'test': str(test.id),
            'positive_answer': test.positive_answer,
            'negative_answer': test.negative_answer,
        } for test in Test.objects.filter(group_test='IOS')]

        response = self.client.post(url, {'competencies': another, **data}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(url, {'competencies': random, **data}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(url, {'competencies': correct, **data}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        account = Account.objects.get(email=data['email'])
        self.assertIsNotNone(account.client_profile)
        self.assertIsNotNone(account.partner_profile)

        # limpiando...
        account.client_profile.delete()
        account.partner_profile.delete()
        account.delete()

    def test_authentication(self):
        """
        Ensure user can authenticate.
        """
        url = reverse('token-auth', kwargs={'version':'dev'})

        data =  {'email': 'user1@asilinks.com', 'password': 'p4ss'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data =  {'email': 'user1@asilinks.com', 'password': '1234'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password(self):
        """
        Ensure user can reset his password.
        """
        url = reverse('password-reset', kwargs={'version':'dev'})

        data =  {'email': 'user1@asilinks.com'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        data =  {'email': 'not_registered@asilinks.com'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contact_us(self):
        """
        Ensure user can send contact messages.
        """
        url = reverse('contact-us', kwargs={'version':'dev'})

        data =  {'subject': 'Tengo pregunta...', 'message': 'No entiendo esto...',
            'from_email': 'not_authenticated@asilinks.com'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_list_locations(self):
        """
        Ensure user can get list locations.
        """
        params = '?alpha2_code=ve'

        url = reverse('location-list', kwargs={'version':'dev'})
        response = self.client.get(url + params)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse('location-tree-format', kwargs={'version':'dev'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse('location-countries', kwargs={'version':'dev'})
        response = self.client.get(url + params)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SelfResourcesTests(APISimpleTestCase):
    def setUp(self):
        super().setUp()

        account = Account.objects.get(email='user1@asilinks.com')
        self.client.force_authenticate(account)

    def test_suggest_us(self):
        """
        Ensure user can send suggestions.
        """
        url = reverse('suggest-us', kwargs={'version':'dev'})

        data =  {'subject': 'Sugerencia...', 'message': 'Mi propuesta de mejora...'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_invite_client(self):
        """
        Ensure user can send invitation mails.
        """
        url = reverse('invite-client', kwargs={'version':'dev'})

        data =  {'receiver_name': 'Cliente Potencial', 'email': 'not_registered@asilinks.com'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # intentando enviar invitacion a correo ya registrado.
        data =  {'receiver_name': 'Cliente Potencial', 'email': 'user2@asilinks.com'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password(self):
        """
        Ensure user can change password.
        """
        url = reverse('self-account-change-password', kwargs={'version':'dev'})

        data =  {'password': 'sample', 'password_2': 'sample'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        account = Account.objects.get(email='user1@asilinks.com')
        self.assertTrue(account.check_password(data['password']))
        account.set_password('p4ss')

        # probando validador de cambio de contraseña.
        data =  {'password': 'sample', 'password_2': 'sample_err'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_email(self):
        """
        Ensure user can change email.
        """
        url = reverse('self-account-change-email', kwargs={'version':'dev'})

        data =  {'email': 'new_user@asilinks.com'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # intentando cambiar a correo ya registrado.
        data =  {'email': 'user2@asilinks.com'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_self_account(self):
        """
        Ensure user can retrieve his personal info.
        """
        url = reverse('self-account-detail', kwargs={'version':'dev'})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_self_account(self):
        """
        Ensure user can update his personal info.
        """
        url = reverse('self-account-detail', kwargs={'version':'dev'})
        location = Location.objects.get(state='Miranda')

        # probando actualizacion base.
        data =  {'paypal_email': 'user1@asilinks.com', 'first_name': 'Alejandro',
            'last_name': 'Borges', 'gender': 'M', 'residence': location.id,
            'commercial_sector': 'Agricultura'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        account = Account.objects.get(email='user1@asilinks.com')
        self.assertEqual(account.client_profile.commercial_sector, data['commercial_sector'])

        # probando validador de birth_date.
        data =  {'birth_date': '2010-01-01'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_legal_docs(self):
        """
        Ensure user can retrieve his legal info.
        """
        url = reverse('self-account-legal-docs', kwargs={'version':'dev'})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_legal_docs(self):
        """
        Ensure user can update his legal info.
        """
        url = reverse('self-account-legal-docs', kwargs={'version':'dev'})

        # data de persona juridica
        data = {
            "juridical_person": True,
            "company_name": "Coca Cola C.A.",
            "company_id": "J-123456789",
            "record_name": "Nombre de registro...",
            "record_number": "Numero de registro",
            "constitutive_doc": "Mas info...",
            "constitutive_date": "1995-04-26",
            "constitutive_country": "VE",
            "legal_representative": "Fulano de Tal",
            "partners_name": [
                "Pedro Alvarez", "Juan Sevilla"
            ]
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # data de persona natural
        data = {
            "juridical_person": False,
            "identity_document": "19564723",
            "nationality": "VE",
            "professional_reference": "Ingeniero en Sistemas",
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_list_devices(self):
        """
        Ensure usar can list devices registered.
        """
        url = reverse('self-account-devices', kwargs={'version':'dev'})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_register_device(self):
        """
        Ensure usar can register devices.
        """
        url = reverse('self-account-devices', kwargs={'version':'dev'})

        data = {
            "type": "web",
            "registration_id": "fSacbcK7yGY:APA91bGPN4b_7PyyAjOhIYPiweMcyMrJU3739m9KcaClb3qSDuQROkPCBtiUULkxyZ2P5mLajQ8lHUlMAy1ezmODQU3n6HMw_1F3E0DRmSE5qqIi84bsgrFbUVkMi1HX47YYdtuKC4mR"
        }
        FCMDevice.objects.filter(registration_id=data['registration_id']).delete()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # intentando registrarlo nuevamente.
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

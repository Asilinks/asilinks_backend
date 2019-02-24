
from rest_framework.test import APISimpleTestCase, APIClient
from rest_framework.reverse import reverse
from rest_framework import status

from .documents import Request
from main.documents import Client, Partner
from authentication.documents import Account

# Create your tests here.

class RequestConsistencyTests(APISimpleTestCase):

    def test_request_todo_status(self):
        """
        Ensure request in todo status are consistence.
        """

        for request in Request.objects.all():
            with self.subTest(request=request):
                if request.status == Request.STATUS_TODO:
                    self.assertIsNone(request.partner)
                    self.assertNotIn(request, request.client.requests_in_progress,
                        msg='{}'.format(request.id))
                    self.assertNotIn(request, request.client.requests_canceled,
                        msg='{}'.format(request.id))
                    self.assertNotIn(request, request.client.requests_done,
                        msg='{}'.format(request.id))
                    self.assertIn(request, request.client.requests_todo,
                        msg='{}'.format(request.id))

class RequestWorkflowTests(APISimpleTestCase):
    def setUp(self):
        super().setUp()

        for item in ('user1', 'user2', 'user3', 'user4',):
            client = APIClient()
            account = Account.objects.get(email='{}@asilinks.com'.format(item))
            client.force_authenticate(account)
            setattr(self, item, client)

    def test_create_request(self):

        url = reverse('request-list', kwargs={'version':'dev'})
        data = {
            'know_fields': ['591c6dafe6e8da00d7b9ce82', '591c6db9e6e8da00d7b9ce83'],
            'description': 'estos son muchos detalles del requerimiento de derecho...',
            'name': 'Tengo otra solicitud',
        #     'country': 'AR',
        }
        response = self.user1.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
            msg=response.json())

        self.assertEqual(response.json()['status'], Request.STATUS_TODO,
            msg=response.json())

        req = Request.objects.get(id=response.json()['id'])
        self.assertIn(req, req.client.requests_todo, msg=req.id)

        # Selected round_partners
        for r_partner in req.round_partners:
            with self.subTest(r_partner=r_partner):
                self.assertIn(req, r_partner.partner.requests_todo, msg=req.id)


        url = reverse('request-send-message', kwargs={'version':'dev', 'id': req.id})
        data = {
            'type': 'text',
            'content':"pregunta del documento...",
        }

        q1 = self.user4.post(url, data)
        self.assertEqual(q1.status_code, status.HTTP_200_OK,
            msg=q1.json())

        data = {
            'type': 'text',
            'content':"respondo a la pregunta.",
            'reference_ts': q1.json()['questions'][0]['ts'],
        }
        r1 = self.user1.post(url, data)
        self.assertEqual(r1.status_code, status.HTTP_200_OK,
            msg=r1.json())

        # Retry send response to same message.
        r2 = self.user1.post(url, data)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST,
            msg=r2.json())

        # Sending offers.
        url = reverse('request-send-offer', kwargs={'version':'dev', 'id': req.id})
        data = {
            'price': 250, 
            'description': 'Tarderé lo necesario para realizar este trabajo.',
            'duration': 100, 
            'requisites': [
                'necesito esto',
                'necesito aquello'
            ]
        }
        response = self.user4.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK,
            msg=response.json())

        data = {
            'price': 500, 
            'description': 'Esto es lo que voy a hacer...',
            'duration': 600, 
            'requisites': [
                'solo necesito esto....',
            ]
        }
        response = self.user2.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK,
            msg=response.json())

        url = reverse('request-reject', kwargs={'version':'dev', 'id': req.id})
        response = self.user3.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT,
            msg=response)

        url = reverse('request-detail', kwargs={'version':'dev', 'id': req.id})
        response = self.user3.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
            msg=response.json())

import datetime as dt
import pandas as pd
from pytz import utc

from django.conf import settings
from django.utils.translation import ugettext as _
from mongoengine import fields, document, DENY, NULLIFY
from django.contrib.auth.hashers import check_password

from asilinks.fields import LocalStorageFileField, DateField
from asilinks.storage_backends import PublicOverrideMediaStorage
from authentication.models import AbstractUser


class LegalDocs(document.EmbeddedDocument):
    juridical_person = fields.BooleanField(default=False)

    # natural data
    identity_document = fields.StringField(max_length=20)
    nationality = fields.StringField(max_length=2)
    professional_reference = fields.StringField(max_length=50)

    # juridical data
    company_name = fields.StringField(max_length=200)
    company_id = fields.StringField(max_length=20)
    record_name = fields.StringField(max_length=200)
    record_number = fields.StringField(max_length=20)
    constitutive_doc = fields.StringField(max_length=200)
    constitutive_date = DateField()
    constitutive_country = fields.StringField(max_length=2)
    legal_representative = fields.StringField(max_length=200)
    partners_name = fields.ListField(fields.StringField(max_length=50))


class SponsorStatisticalSummary(document.EmbeddedDocument):
    client_interval_average = fields.IntField()
    partner_interval_average = fields.IntField()
    client_rating_average = fields.FloatField()
    partner_rating_average = fields.FloatField()
    client_referred_count = fields.IntField()
    partner_referred_count = fields.IntField()
    monthly_referred_average = fields.FloatField()


class Location(document.Document):
    country = fields.StringField(max_length=50)
    alpha2_code = fields.StringField(max_length=2)
    state = fields.StringField(max_length=50)

    def __str__(self):
        return '{}, {}'.format(self.state, self.country)


class Account(AbstractUser):
    LEVEL_A = 'a'
    LEVEL_B = 'b'
    LEVEL_C = 'c'

    LEVEL_CHOICES = (
        (LEVEL_A, _('A')),
        (LEVEL_B, _('B')),
        (LEVEL_C, _('C')),
    )

    GENDER_FEMALE = 'F'
    GENDER_MALE = 'M'
    GENDER_NEUTRAL = 'N'

    GENDER_CHOICES = (
        GENDER_FEMALE,
        GENDER_MALE,
        GENDER_NEUTRAL,
    )

    sponsor = fields.ReferenceField('self', reverse_delete_rule=DENY)
    partner_profile = fields.ReferenceField('Partner')
    client_profile = fields.ReferenceField('Client')
    password_history = fields.ListField(fields.StringField())
    last_password_change = DateField()
    gender = fields.StringField(choices=GENDER_CHOICES, default=GENDER_NEUTRAL)
    paypal_email = fields.EmailField()
    email_confirmed = fields.BooleanField(default=False)
    residence = fields.ReferenceField('Location', reverse_delete_rule=NULLIFY)
    birth_date = DateField()
    legal_docs = fields.EmbeddedDocumentField('LegalDocs')
    avatar = LocalStorageFileField(upload_to='avatars/',
        default='avatars/default.png', storage=PublicOverrideMediaStorage())
    sponsor_level = fields.StringField(choices=LEVEL_CHOICES, default=LEVEL_C)
    sponsor_statistical_summary = fields.EmbeddedDocumentField('SponsorStatisticalSummary')

    def get_initials(self):
        fn = self.first_name[0].upper() if self.first_name else ''
        ln = self.last_name[0].upper() if self.first_name else ''
        return '{}{}'.format(fn, ln)

    @property
    def devices(self):
        from fcm.documents import FCMDevice
        return FCMDevice.objects.filter(owner=self)
    
    @property
    def utc_last_login(self):
        return utc.localize(self.last_login)

    def send_message(self, *args, **kwargs):
        return self.devices.send_message(*args, **kwargs)

    def has_partner_profile(self):
        return bool(self.partner_profile)

    @classmethod
    def default_fee_account(cls):
        return cls.objects.get(email=settings.DEFAULT_EMAIL_COMMISSIONS)

    @classmethod
    def default_sponsor_account(cls):
        return cls.objects.get(email=settings.DEFAULT_EMAIL_SPONSOR)

    @classmethod
    def paypal_fee_account(cls):
        return cls.objects.get(email=settings.PAYPAL_ACCOUNT)

    def match_last_passwords(self, new_pass):
        """
        Given a new password, it checks if it is equal to the past five
        """
        return any(check_password(new_pass, password) for password in self.get_last_passwords())

    def get_last_passwords(self):
        """
        Returns the past five passwords
        """
        return self.password_history[-5:] if self.password_history else list()

    def update_sponsor_statistical_summary(self):
        summary = {'monthly_referred_average': 0,
            'client_referred_count': 0, 'client_rating_average': 0,
            'partner_referred_count': 0, 'partner_rating_average': 0, 
            'client_interval_average': 0, 'partner_interval_average': 0,
        }

        referred_clients = pd.DataFrame([{
            'has_partner_profile': ref.has_partner_profile(),
            'date_joined': ref.date_joined,
            'client_rating': ref.client_profile.rating,
            'partner_rating': ref.partner_profile.rating if ref.has_partner_profile() else None,
        } for ref in Account.objects.filter(sponsor=self)])

        if referred_clients.empty:
            self.modify(sponsor_statistical_summary=summary)
            return

        diff_clients = (referred_clients['date_joined'].shift(-1)
            - referred_clients['date_joined']).dropna()
        summary.update({
            'client_referred_count': len(referred_clients),
            'client_rating_average': referred_clients['client_rating'].mean(),
            'client_interval_average': diff_clients.mean() // pd.Timedelta(1, 'h') if not diff_clients.empty else 0,
            'monthly_referred_average': referred_clients['client_rating'].groupby(
                referred_clients['date_joined'].map(lambda x: dt.datetime(x.year, x.month, 1))).count().mean(),
        })

        referred_partners = referred_clients.query('has_partner_profile == True')
        if not referred_partners.empty:
            diff_partners = (referred_partners['date_joined'].shift(-1)
                - referred_partners['date_joined']).dropna()
            summary.update({
                'partner_referred_count': len(referred_partners),
                'partner_rating_average': referred_partners['partner_rating'].mean(),
                'partner_interval_average': diff_partners.mean() // pd.Timedelta(1, 'h') if not diff_partners.empty else 0,
            })

        self.modify(sponsor_statistical_summary=summary)

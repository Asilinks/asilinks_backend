import datetime as dt
from functools import reduce

from django.conf import settings
from django.utils.translation import ugettext as _
from mongoengine import fields, document, CASCADE, NULLIFY, PULL

from asilinks.storage_backends import PublicOverrideMediaStorage, PrivateMediaStorage
from asilinks.fields import LocalStorageFileField
from admin.notification import CLIENT_MESSAGES, PARTNER_MESSAGES
from authentication.documents import Account


__all__ = ['Client', 'Partner', 'AcademicOptions', 'PartnerStatisticalSummary',
    'Academic', 'Test', 'Category', 'KnowField', 'Competence', 'FavoritePartner',
    'PartnerSkill']


class KnowField(document.Document):
    about = fields.StringField()
    enable = fields.BooleanField(default=False)
    category = fields.StringField()
    sub_category = fields.StringField()

    def __str__(self):
        return '{} - {}'.format(self.category, self.sub_category)


class Client(document.Document):
    account = fields.ReferenceField('Account', reverse_delete_rule=CASCADE)
    rating = fields.DecimalField(min_value=0, default=0)
    commercial_sector = fields.StringField(max_length=50)
    residence = fields.ReferenceField('Location', reverse_delete_rule=NULLIFY)
    favorite_partners = fields.EmbeddedDocumentListField('FavoritePartner')
    last_activity = fields.DateTimeField()

    requests_todo = fields.ListField(fields.ReferenceField('Request'))
    requests_in_progress = fields.ListField(fields.ReferenceField('Request'))
    requests_done = fields.ListField(fields.ReferenceField('Request'))
    requests_canceled = fields.ListField(fields.ReferenceField('Request'))
    requests_draft = fields.EmbeddedDocumentListField('DraftRequest')

    def __str__(self):
        return self.account.get_full_name()

    def update_rating(self):
        requests_reviewed = [
            *[r.client_review.score for r in self.requests_done if r.client_review],
            *[r.client_review.score for r in self.requests_canceled if r.client_review]]

        if requests_reviewed:
            self.modify(rating=sum(requests_reviewed) / len(requests_reviewed))

Client.register_delete_rule(Account, 'client_profile', NULLIFY)


class PartnerStatisticalSummary(document.EmbeddedDocument):
    done_count = fields.IntField()
    done_time_average = fields.FloatField()
    canceled_count = fields.IntField()
    offered_percent = fields.FloatField()
    done_score_average = fields.FloatField()
    academics_count = fields.IntField()
    experience_years = fields.IntField()
    accept_time_average = fields.FloatField()
    price_average = fields.FloatField()


class Partner(document.Document):

    LEVEL_BLACK = 'black'
    LEVEL_PLATINUM = 'platinum'
    LEVEL_GOLD = 'gold'
    LEVEL_SILVER = 'silver'
    LEVEL_BRONZE = 'bronze'

    LEVEL_CHOICES = (
        (LEVEL_BLACK, _('Negro')),
        (LEVEL_PLATINUM, _('Platino')),
        (LEVEL_GOLD, _('Oro')),
        (LEVEL_SILVER, _('Plata')),
        (LEVEL_BRONZE, _('Bronce')),
    )

    account = fields.ReferenceField('Account', reverse_delete_rule=CASCADE)
    rating = fields.DecimalField(min_value=0, default=0)
    residence = fields.ReferenceField('Location', reverse_delete_rule=NULLIFY)
    level = fields.StringField(choices=LEVEL_CHOICES, default=LEVEL_BRONZE)
    curricular_abstract = fields.StringField(db_field='stract', max_length=500)
    academics = fields.EmbeddedDocumentListField('Academic')
    experience_years = fields.IntField(min_value=0, default=0)
    tests_review = fields.EmbeddedDocumentListField('TestReview')
    know_fields = fields.ListField(
        fields.ReferenceField('KnowField', reverse_delete_rule=PULL))
    joined_date = fields.DateTimeField()
    enabled = fields.BooleanField(default=True)
    levelup_chance = fields.BooleanField(default=False)

    requests_todo = fields.ListField(fields.ReferenceField('Request'))
    requests_in_progress = fields.ListField(fields.ReferenceField('Request'))
    requests_rejected = fields.ListField(fields.ReferenceField('Request'))
    requests_done = fields.ListField(fields.ReferenceField('Request'))
    requests_canceled = fields.ListField(fields.ReferenceField('Request'))

    statistical_summary = fields.EmbeddedDocumentField('PartnerStatisticalSummary')

    def clean(self):
        self.joined_date = dt.datetime.now()

    def __str__(self):
        return self.account.get_full_name()

    def update_rating(self):
        requests_reviewed = [
            *[r.partner_review.score for r in self.requests_done if r.partner_review],
            *[r.partner_review.score for r in self.requests_canceled if r.partner_review]]

        if requests_reviewed:
            self.modify(rating=sum(requests_reviewed) / len(requests_reviewed))

    def update_statistical_summary(self):
        summary = {
            'done_count': len(self.requests_done),
            'canceled_count': len(self.requests_canceled),
            'academics_count': len(self.academics),
            'experience_years': self.experience_years,
        }

        if summary['done_count']:
            summary['done_time_average'] = (reduce((lambda x, y: x + y), 
                [(req.date_closed - req.date_started) for req in self.requests_done],
                dt.timedelta()) / summary['done_count']).total_seconds()

            summary['done_score_average'] = sum([req.partner_review.score if req.partner_review else 0 for req in self.requests_done]) / summary['done_count']
            summary['price_average'] = float(sum([req.price for req in self.requests_done]) / summary['done_count'])
            summary['accept_time_average'] = (reduce((lambda x, y: x + y), 
                [(req.round_partners.get(partner=self).date_response - req.round_partners.get(partner=self).date_notification) for req in self.requests_done],
                dt.timedelta()) / summary['done_count']).total_seconds()
        else:
            summary['done_time_average'] = dt.timedelta().total_seconds()
            summary['accept_time_average'] = dt.timedelta().total_seconds()
            summary['done_score_average'] = 0
            summary['price_average'] = 0

        not_selected = [req.round_partners.get(partner=self).price != None for req in self.requests_rejected]

        if len(not_selected) + summary['done_count']:
            summary['offered_percent'] = (sum(not_selected) + summary['done_count']) / (len(not_selected) + summary['done_count'] )
        else:
            summary['offered_percent'] = 0

        self.modify(statistical_summary=summary)

    @property
    def has_levelup_chance(self):
        if self.levelup_chance:
            retry_is_unavailable = [test.date + dt.timedelta(days=settings.RETRY_TEST_TIME) > dt.datetime.now()
                for test in self.tests_review.filter(group_test=TestReview.TEST_MAP[self.level], approve=False)]

            return not any(retry_is_unavailable)
        return False

    def change_level(self, new_level):
        level_weights = {self.LEVEL_BRONZE: 1, self.LEVEL_SILVER: 2, self.LEVEL_GOLD: 3}

        if self.level == new_level:
            return
        elif level_weights[self.level] > level_weights[new_level]:
            self.modify(level=new_level)
            self.account.send_message(context={'partner': self}, **PARTNER_MESSAGES['level_down'])
        else:
            tests = self.tests_review.filter(
                group_test=TestReview.TEST_MAP[self.level])

            if not tests:
                self.modify(levelup_chance=True)
                self.account.send_message(context={'partner': self}, **PARTNER_MESSAGES['test_available'])
            elif tests.filter(approve=True):
                self.modify(level=new_level)
                self.account.send_message(context={'partner': self}, **PARTNER_MESSAGES['level_back'])


Partner.register_delete_rule(Account, 'partner_profile', NULLIFY)


class FavoritePartner(document.EmbeddedDocument):
    partner = fields.ReferenceField('Partner')
    know_field = fields.ReferenceField('KnowField')

    def __str__(self):
        return '{} > {}'.format(self.partner.account.email, self.know_field.sub_category)


class Academic(document.EmbeddedDocument):
    college = fields.StringField(max_length=100)
    career = fields.StringField(max_length=100)
    speciality = fields.StringField(max_length=100)


class AcademicOptions(document.Document):
    college = fields.ListField(fields.StringField(max_length=100), required=True)
    career = fields.ListField(fields.StringField(max_length=100), required=True)
    speciality = fields.ListField(fields.StringField(max_length=100), required=True)


class Test(document.Document):
    question = fields.StringField(max_length=200)
    group_test = fields.StringField(max_length=20)
    answers = fields.ListField(fields.StringField(max_length=200))
    positive_answer = fields.IntField()
    negative_answer = fields.IntField()

    def __str__(self):
        return '{}'.format(self.group_test)


class TestReview(document.EmbeddedDocument):
    group_test = fields.StringField(max_length=20)
    date = fields.DateTimeField()
    test_score = fields.IntField(default=0)
    approve = fields.BooleanField()
    competencies = fields.EmbeddedDocumentListField('Competence')

    TEST_MAP = {
        Partner.LEVEL_BRONZE: 'IOS',
        Partner.LEVEL_SILVER: 'IOE'
    }

    def clean(self):
        group_test = {c.test.group_test for c in self.competencies}

        if len(group_test) > 1 or self.group_test not in group_test:
            raise TestReview.GroupTestError()

        if len({c.test for c in self.competencies}) != len(self.competencies):
            raise TestReview.CompetenceRepeated()

        self.test_score = sum([c.evaluate() for c in self.competencies])
        self.approve = self.test_score >= settings.TESTS_THRESHOLD[self.group_test]
        self.date = dt.datetime.now()

    class GroupTestError(BaseException):
        pass

    class CompetenceRepeated(BaseException):
        pass


class Competence(document.EmbeddedDocument):
    test = fields.ReferenceField('Test', required=True)
    positive_answer = fields.IntField(required=True)
    negative_answer = fields.IntField()

    def evaluate(self):
        evaluate_test = 'evaluate_' + self.test.group_test

        if not hasattr(self, evaluate_test):
            raise Exception(self.test.group_test + ' has not evaluation function.')

        return getattr(self, evaluate_test)()

    def evaluate_BASE(self):
        positive = 1 if self.positive_answer == self.test.positive_answer else 0
        negative = 1 if self.negative_answer == self.test.negative_answer else 0
        return positive + negative

    def evaluate_IOS(self):
        return 1 if self.positive_answer == self.test.positive_answer else 0

    def evaluate_IOE(self):
        value = 6 if self.positive_answer > 3 else 1
        return 1 if value == self.test.positive_answer else 0


class Category(document.Document):
    name = fields.StringField(unique=True)
    about = fields.StringField()
    enable = fields.BooleanField(default=False)
    image = LocalStorageFileField(upload_to='categories/',
        default='categories/default.png', storage=PublicOverrideMediaStorage())
    related_categories = fields.ListField(fields.ReferenceField('self',
        reverse_delete_rule=PULL))

    meta = {'indexes': [
        {'fields': ['$name', "$about"],
         'default_language': 'spanish',
         'weights': {'name': 10, 'about': 2}
         }
    ]}

    @property
    def know_fields(self):
        return KnowField.objects.filter(category=self.name)
    
    def __str__(self):
        return self.name


class PartnerSkill(document.Document):
    know_field = fields.ReferenceField('KnowField',
        reverse_delete_rule=CASCADE)
    name = fields.StringField()


class ExtraDescription(document.EmbeddedDocument):
    english_level = fields.StringField(max_length=20)
    estimated_duration = fields.StringField(max_length=50)
    advance_notion = fields.StringField(max_length=20)
    skills = fields.ListField(fields.StringField())


class DraftRequest(document.EmbeddedDocument):
    name = fields.StringField(max_length=100)
    know_fields = fields.ListField(fields.ReferenceField('KnowField'))
    description = fields.StringField(max_length=4000)
    extra_description = fields.EmbeddedDocumentField('ExtraDescription')
    country_alpha2 = fields.StringField(max_length=2, default=None)
    attachment = LocalStorageFileField(upload_to='drafts/%Y%m%d/',
        storage=PrivateMediaStorage())
    date = fields.DateTimeField()

import os
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.translation import ugettext as _
from mongoengine import fields, document, CASCADE, NULLIFY, DENY, PULL

from asilinks.fields import TimeDeltaField, LocalStorageFileField
from asilinks.storage_backends import PrivateMediaStorage

from main.documents import Client, Partner, FavoritePartner
from admin.documents import DeliverableStore
from admin.notification import PARTNER_MESSAGES
from payments.documents import Transaction, Bill
from payments.interfaces import get_interface


class Review(document.EmbeddedDocument):
    score = fields.IntField(min_value=0, max_value=10, default=0)
    comments = fields.StringField()


class Request(document.Document):

    STATUS_TODO = 1
    STATUS_IN_PROGRESS = 2
    STATUS_DELIVERED = 3
    STATUS_PENDING = 4
    STATUS_DONE = 5
    STATUS_CANCELED = 6
    STATUS_UNSATISFIED = 7

    STATUS_CHOICES = (
        (STATUS_TODO, _('iniciado')),
        (STATUS_IN_PROGRESS, _('en progreso')),
        (STATUS_DELIVERED, _('entregado')),
        (STATUS_PENDING, _('pagado')),
        (STATUS_DONE, _('culminado')),
        (STATUS_CANCELED, _('cancelado')),
        (STATUS_UNSATISFIED, _('insatisfecho')),
    )

    name = fields.StringField(max_length=100)
    know_fields = fields.ListField(fields.ReferenceField('KnowField', reverse_delete_rule=DENY))
    description = fields.StringField(max_length=4000)
    extra_description = fields.EmbeddedDocumentField('ExtraDescription')
    country_alpha2 = fields.StringField(max_length=2, default=None)
    client = fields.ReferenceField('Client', reverse_delete_rule=CASCADE)
    last_read_client = fields.DateTimeField(default=dt.datetime.now)
    partner = fields.ReferenceField('Partner', reverse_delete_rule=CASCADE)
    last_read_partner = fields.DateTimeField(default=dt.datetime.now)
    price = fields.DecimalField(min_value=0,
        precision=2, rounding=ROUND_HALF_UP)
    sponsor_percent = fields.DecimalField(precision=3)

    client_review = fields.EmbeddedDocumentField('Review')
    partner_review = fields.EmbeddedDocumentField('Review')
    status = fields.IntField(choices=STATUS_CHOICES, default=STATUS_TODO)
    round_partners = fields.EmbeddedDocumentListField('RoundPartner')
    date_created = fields.DateTimeField()
    date_started = fields.DateTimeField()
    date_delivered = fields.DateTimeField()
    date_closed = fields.DateTimeField()
    date_canceled = fields.DateTimeField()
    date_promise = fields.DateTimeField()
    date_unsatisfied = fields.DateTimeField()

    com_channel = fields.EmbeddedDocumentListField('Message')
    questions = fields.EmbeddedDocumentListField('Message')
    transactions = fields.ListField(
        fields.ReferenceField('Transaction'), reverse_delete_rule=PULL)
    time_extensions = fields.EmbeddedDocumentListField('TimeExtension')

    def __str__(self):
        return '{} > {}'.format(self.name, self.know_fields)

    @classmethod
    def create_from_draft(cls, draft, client):
        attachment = getattr(draft, 'attachment', None)

        data = {
            'client': client,
            'date_created': dt.datetime.now(),
            **{key: getattr(draft, key, None) 
                for key in ('name', 'know_fields', 'description',
                    'extra_description', 'country_alpha2',)}
        }
        instance = cls.objects.create(**data)

        if attachment:
            filename = os.path.split(attachment.file.name)[-1]
            content = ContentFile(attachment.file.read())

            message = Message(ts=dt.datetime.now(), owner=client.account,
                type=Message.TYPE_DOC)
            message.attachment.save(filename, content, save=False)
            attachment.file.close()

            instance.modify(push__questions=message)

        instance.client.modify(push__requests_todo=instance, last_activity=dt.datetime.now())
        from .tasks import select_round_partners
        select_round_partners(str(instance.id))
        # result = select_round_partners.delay(str(instance.id))

        draft.attachment.delete()
        client.modify(pull__requests_draft__date=draft.date)
        return instance

    @property
    def penalty_discount(self):
        discount = settings.PENALTY_DISCOUNT

        if not self.date_promise:
            return 0
        diference = (self.date_delivered or dt.datetime.now()) - self.date_promise
        return discount[max(0, min(diference.days, len(discount)-1))]

    def calculate_bill(self, round_partner=None, interface=None):
        request_fees = settings.PAYMENT_CONSTANTS['request_fees']
        first_client_payment = settings.PAYMENT_CONSTANTS['first_client_payment']

        if interface is None:
            interface = self.transactions[0].interface
        payment_interface = get_interface(interface)

        if self.partner is not None:
            price = ((1 - self.penalty_discount) * self.price).quantize(
                Decimal('.01'), rounding=ROUND_HALF_UP)
            asilinks_percent = request_fees['total_fee'] - self.sponsor_percent
        else:
            sponsor = self.client.account.sponsor
            rate_partner = {'gold': 2, 'silver': 1, 'bronze': 0}
            rate_sponsor = {'a': 0, 'b': 1, 'c': 2}

            partner = round_partner.partner
            price = round_partner.price
            asilinks_percent = (request_fees['max_asilinks_fee']
                - rate_partner[partner.level] * request_fees['asilinks_fee_rate']
                + rate_sponsor[sponsor.sponsor_level] * request_fees['sponsor_fee_rate'])

        payout_fee = (payment_interface.calculate_payout_fee(price)
            + payment_interface.calculate_payout_fee(price * (request_fees['total_fee']
            - asilinks_percent)))

        asilinks_pay = (price * asilinks_percent).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP)

        fee_amount = (price * request_fees['total_fee']).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP)

        sponsor_pay = fee_amount - asilinks_pay

        result = {
            'partner': price,
            'asilinks': asilinks_pay,
            'sponsor': sponsor_pay,
            'sponsor_percent': request_fees['total_fee'] - asilinks_percent
        }

        if self.status == Request.STATUS_TODO:
            first_payment = ((price + fee_amount + payout_fee) * first_client_payment).quantize(
                Decimal('.01'), rounding=ROUND_HALF_UP)
            second_payment = price + fee_amount + payout_fee - first_payment
            to_pay = payment_interface.calculate_payment_fee(first_payment) + first_payment
            paypal_pay = payment_interface.calculate_payment_fee(first_payment) + \
                payment_interface.calculate_payment_fee(second_payment) + payout_fee

            result.update({
                'paypal': paypal_pay,
                'total': price + fee_amount + paypal_pay,
                'to_pay': to_pay,
            })

        elif self.status in (Request.STATUS_DELIVERED, Request.STATUS_IN_PROGRESS):
            first_payment, first_paypal_fee = self.transactions[0].payment_plus_fee

            second_payment = price + fee_amount + payout_fee - first_payment
            paypal_pay = first_paypal_fee + payout_fee + \
                payment_interface.calculate_payment_fee(second_payment)
            to_pay = payment_interface.calculate_payment_fee(second_payment) + second_payment

            result.update({
                'paypal': paypal_pay,
                'total': price + fee_amount + paypal_pay,
                'to_pay': to_pay,
            })

        else:
            amounts, paypal_fees = zip(
                *[t.payment_plus_fee for t in self.transactions])

            result.update({
                'paypal': sum(paypal_fees) + payout_fee,
                'total': sum(amounts) + sum(paypal_fees),
                'to_pay': Decimal('0'),
            })

        return result

    def close(self):
        bill = self.calculate_bill()
        common = {
            'item': self,
            'interface': self.transactions[0].interface,
        }

        transactions = [
            Transaction.make_transaction(
                    amount=bill['partner'],
                    operation=Transaction.OP_PARTNER_SETTLEMENT,
                    owner=self.partner.account,
                    **common
                ),
            Transaction.make_transaction(
                    amount=bill['sponsor'],
                    operation=Transaction.OP_SPONSOR_FEE,
                    owner=self.client.account,
                    **common
                ),
            Transaction.make_transaction(
                    amount=bill['asilinks'],
                    operation=Transaction.OP_ASILINKS_FEE,
                    owner=self.client.account,
                    **common
                ),
            Transaction.make_transaction(
                    amount=bill['paypal'],
                    operation=Transaction.OP_PAYPAL_FEE,
                    owner=self.client.account,
                    **common
                ),
        ]

        self.client.modify(
            pull__requests_in_progress=self,
            push__requests_done=self,
            last_activity=dt.datetime.now())
        self.partner.modify(
            pull__requests_in_progress=self,
            push__requests_done=self)
        self.modify(push_all__transactions=transactions,
            status=self.STATUS_DONE, date_closed=dt.datetime.now())

        Bill.make_bill(self)
        DeliverableStore.store_request(self)

        # Send message to partner, request was satisfied
        self.partner.account.send_message(context={'request': self},
            data={'request_id': str(self.id), 'profile': 'partner'},
            **PARTNER_MESSAGES['client_satisfied'])

    def refund(self):
        if self.status in (self.STATUS_TODO, self.STATUS_DONE, self.STATUS_CANCELED):
            raise ValueError('No se puede dinero en el estado actual que se encuentra el requerimiento.')

        max_asilinks_fee = settings.PAYMENT_CONSTANTS['request_fees']['max_asilinks_fee']
        flat_paypal_fee = settings.PAYMENT_CONSTANTS['paypal_fees']['flat']
        interface = self.transactions[0].interface
        payment_interface = get_interface(interface)
        refund_transactions = []

        asilinks_pay = (self.price * max_asilinks_fee).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP)
        refund_transactions.append(
            Transaction.make_transaction(asilinks_pay, owner=self.client.account,
                operation=Transaction.OP_ASILINKS_FEE, interface=interface, item=self)
        )

        paypal_pay = payment_interface.calculate_payment_fee(asilinks_pay)
        count_payments = sum([r.operation == Transaction.OP_REQUEST_PAYMENT for r in self.transactions])
        paypal_pay += (Decimal('0'), flat_paypal_fee)[count_payments > 1]

        refund_transactions.append(
            Transaction.make_transaction(paypal_pay, owner=self.client.account,
                operation=Transaction.OP_PAYPAL_FEE, interface=interface, item=self)
        )

        commission_charged = False
        for t in self.transactions:
            if not commission_charged:
                refund = t.refund(t.amount - (asilinks_pay + paypal_pay))
                commission_charged = True
            else:
                refund = t.refund()
            refund_transactions.append(refund)

        total_fee = asilinks_pay + paypal_pay
        self.modify(push_all__transactions=refund_transactions)

        return {
            'asilinks': asilinks_pay,
            'paypal': paypal_pay,
            'total': total_fee,
            'refund': self.price - total_fee
        }

    def append_favorite_partner(self):
        common_nf = [item for item in self.know_fields
            if item in self.partner.know_fields]

        for nf in common_nf:
            self.client.favorite_partners.filter(know_field=nf).delete()

        self.client.favorite_partners.extend(
            [FavoritePartner(know_field=know_field, partner=self.partner)
             for know_field in common_nf]
        )

        self.client.save()

    def update_last_read(self, account):
        if self.client == account.client_profile:
            self.modify(last_read_client=dt.datetime.now())

        elif self.status != Request.STATUS_TODO:
            if self.partner == account.partner_profile:
                self.modify(last_read_partner=dt.datetime.now())

        else:
            round_partner = self.round_partners.get(
                partner=account.partner_profile)
            round_partner.last_read = dt.datetime.now()
            self.save()

    def get_last_read(self,account):

        if account.client_profile == self.client:
            return self.last_read_client

        if account.has_partner_profile():
            if account.partner_profile == self.partner:
                return self.last_read_partner

            else:
                return self.round_partners.get(
                    partner=account.partner_profile).last_read

        raise ValueError("This account don't belong to this request")

    def new_messages(self, account):
        last_read = self.get_last_read(account)

        if self.status == self.STATUS_TODO:
            channel = self.questions

        else:
            channel = self.com_channel

        return sum([last_read < message.ts for message in channel])

    def new_offers(self):
        if self.status == self.STATUS_TODO:
            return sum([rp.date_response > self.last_read_client
                for rp in self.round_partners \
                if rp.date_response and rp.rejected == False])

        return 0

    def can_be_canceled(self) -> bool:
        now = dt.datetime.now()

        if self.status == self.STATUS_IN_PROGRESS and \
            self.date_promise + dt.timedelta(days=7) < now:
            return True
        elif self.status == self.STATUS_UNSATISFIED and \
            self.date_unsatisfied < now:
            return True
        return False

Request.register_delete_rule(Client, 'requests_todo', PULL)
Request.register_delete_rule(Client, 'requests_in_progress', PULL)
Request.register_delete_rule(Client, 'requests_done', PULL)
Request.register_delete_rule(Client, 'requests_canceled', PULL)

Request.register_delete_rule(Partner, 'requests_todo', PULL)
Request.register_delete_rule(Partner, 'requests_in_progress', PULL)
Request.register_delete_rule(Partner, 'requests_rejected', PULL)
Request.register_delete_rule(Partner, 'requests_done', PULL)
Request.register_delete_rule(Partner, 'requests_canceled', PULL)


class RoundPartner(document.EmbeddedDocument):
    partner = fields.ReferenceField('Partner')
    date_notification = fields.DateTimeField()
    last_read = fields.DateTimeField(default=dt.datetime.now)
    date_response = fields.DateTimeField()
    rejected = fields.BooleanField(default=False)
    price = fields.DecimalField(min_value=0, 
        precision=2, rounding=ROUND_HALF_UP)
    duration = TimeDeltaField()
    requisites = fields.ListField(fields.StringField(max_length=50))
    description = fields.StringField()
    last_activity = fields.DateTimeField()

    def __str__(self):
        return self.partner.account.email


class Message(document.EmbeddedDocument):

    TYPE_VOICE = 'voice'
    TYPE_IMAGE = 'image'
    TYPE_DOC = 'doc'
    TYPE_TEXT = 'text'

    TYPE_CHOICES = (
        (TYPE_VOICE, _('voice')),
        (TYPE_IMAGE, _('image')),
        (TYPE_DOC, _('doc')),
        (TYPE_TEXT, _('text')),
    )

    CONTENT_TYPES = {
        TYPE_VOICE: (
            'audio/mpeg',
            'audio/mp3',
        ),
        TYPE_IMAGE: (
            'image/jpg',
            'image/jpeg',
            'image/png',
        ),
        TYPE_DOC: (
            'text/plain',
            'application/pdf',
            'application/msword',
            'application/vnd.ms-excel',
            'application/vnd.ms-excel.sheet.macroenabled.12',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
    }

    owner = fields.ReferenceField('Account')
    type = fields.StringField(choices=TYPE_CHOICES, default=TYPE_TEXT)
    content = fields.StringField(max_length=200)
    attachment = LocalStorageFileField(upload_to='attachments/%Y%m%d/',
        storage=PrivateMediaStorage())
    ts = fields.DateTimeField()
    reference_ts = fields.DateTimeField()
    last_delivery = fields.BooleanField(default=False)


class TimeExtension(document.EmbeddedDocument):
    duration = TimeDeltaField()
    excuse = fields.StringField(max_length=200)
    date_created = fields.DateTimeField()
    date_closed = fields.DateTimeField()
    approve = fields.BooleanField(default=None)

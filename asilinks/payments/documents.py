import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils.translation import ugettext as _
from mongoengine import fields, document, CASCADE, NULLIFY, PULL

from authentication.documents import Account
from .interfaces import INTERFACES, get_interface


class Transaction(document.Document):

    TYPE_CREDIT = 'credit'
    TYPE_DEBIT = 'debit'

    TYPE_CHOICES = (
        (TYPE_CREDIT, _('crédito')),
        (TYPE_DEBIT, _('débito')),
    )

    OP_REQUEST_PAYMENT = 1
    OP_PARTNER_SETTLEMENT = 2
    OP_SPONSOR_FEE = 3
    OP_ASILINKS_FEE = 4
    OP_PAYPAL_FEE = 5
    OP_WITHDRAW = 6
    OP_PRODUCT_PAYMENT = 7
    OP_REFUND = 8
    OP_DEBTS_TO_PAY = 9
    OP_ASICOINS_PAYMENT = 10

    OP_CHOICES = (
        (OP_REQUEST_PAYMENT, _('Pago de requerimiento.')),
        (OP_PARTNER_SETTLEMENT, _('Pago al socio.')),
        (OP_SPONSOR_FEE, _('Honorarios del referente.')),
        (OP_ASILINKS_FEE, _('Honorarios de Asilinks.')),
        (OP_PAYPAL_FEE, _('Comisiones de Paypal.')),
        (OP_WITHDRAW, _('Retiro de efectivo.')),
        (OP_PRODUCT_PAYMENT, _('Pago por producto.')),
        (OP_REFUND, _('Reembolso.')),
        (OP_DEBTS_TO_PAY, _('Cuenta por pagar.')),
        (OP_ASICOINS_PAYMENT, _('Pago por Asicoins.')),
    )

    DEBIT_OPS = (
        OP_REQUEST_PAYMENT,
        # OP_WITHDRAW,
        OP_PRODUCT_PAYMENT,
        OP_DEBTS_TO_PAY,
        OP_ASICOINS_PAYMENT,
    )

    CREDIT_OPS = (
        OP_PARTNER_SETTLEMENT,
        OP_SPONSOR_FEE,
        OP_ASILINKS_FEE,
        OP_PAYPAL_FEE,
        OP_REFUND
    )

    INTERFACE_CHOICES = tuple(INTERFACES.keys())

    owner = fields.ReferenceField('Account', reverse_delete_rule=NULLIFY)
    receiver = fields.ReferenceField('Account', reverse_delete_rule=NULLIFY)
    date = fields.DateTimeField()
    type = fields.StringField(choices=TYPE_CHOICES)
    operation = fields.IntField(choices=OP_CHOICES)
    interface = fields.StringField(choices=INTERFACE_CHOICES)
    amount = fields.DecimalField(min_value=0)
    external_reference = fields.StringField(max_length=50)
    item = fields.GenericReferenceField()

    meta = { 'ordering': ['-date'] }

    def __str__(self):
        sign = '+' if self.type == Transaction.TYPE_CREDIT else '-'
        return '{}: {} -> {}{}'.format(self.get_operation_display(), 
            self.owner.email, sign, self.amount, )

    @classmethod
    def make_transaction(cls, amount, operation, owner, **kwargs):

        if not isinstance(owner, Account):
            raise ValueError('The owner must be Account instance')

        data = {
            'date': dt.datetime.now(),
            'amount': amount,
            'operation': operation,
            'owner': owner,
            'item': kwargs.get('item'),
            'interface': kwargs.get('interface')
        }
        payment_interface = get_interface(data['interface'])

        if operation in cls.CREDIT_OPS:
            data['type'] = cls.TYPE_CREDIT

            if operation == cls.OP_PARTNER_SETTLEMENT:
                data['external_reference'] = payment_interface.make_payout(
                    receiver=owner, amount=amount)

            elif operation == cls.OP_SPONSOR_FEE:
                data['receiver'] = owner.sponsor
                if owner.sponsor != Account.default_sponsor_account():
                    data['external_reference'] = payment_interface.make_payout(
                        receiver=data['receiver'], amount=amount)

            elif operation == cls.OP_REFUND:
                data['external_reference'] = kwargs['external_reference']

            return cls.objects.create(**data)

        elif operation in cls.DEBIT_OPS:
            data['type'] = cls.TYPE_DEBIT

            data['external_reference'] = payment_interface.make_payment(
                amount=amount, **kwargs)
            return cls.objects.create(**data)

        else:
            raise ValueError('The operation is not registered.')

    @classmethod
    def make_debts_to_pay(cls, client):
        from requesting.documents import Request
        reqs_delivered = Request.objects.filter(client=client,
            status=Request.STATUS_DELIVERED)

        return [cls(owner=client.account, date=dt.datetime.now(), 
            type=cls.TYPE_DEBIT, operation=cls.OP_DEBTS_TO_PAY, item=req,
            amount=req.calculate_bill()['to_pay']) for req in reqs_delivered]

    def refund(self, amount=None):
        if amount is None:
            amount = self.amount

        refund_ref = get_interface(self.interface).make_refund(
            sale_id=self.external_reference, amount=amount)
        kwargs = {
            'external_reference': refund_ref,
            'interface': self.interface,
            'item': self.item,
        }

        return Transaction.make_transaction(amount,
            self.OP_REFUND, self.owner, **kwargs)

    @property
    def payment_plus_fee(self):
        fees = settings.PAYMENT_CONSTANTS['paypal_fees']

        if self.operation != Transaction.OP_REQUEST_PAYMENT:
            return Decimal('0'), Decimal('0')

        else:
            paypal = (self.amount * fees['percent']
                + fees['flat']).quantize(
                Decimal('.01'), rounding=ROUND_HALF_UP)
            return self.amount - paypal, paypal


class Bill(document.Document):

    FEATURE_REQUEST = 1
    FEATURE_PRODUCT = 2
    FEATURE_ASICOINS = 3

    FEATURE_CHOICES = (
        (FEATURE_REQUEST, _('Pago por requerimiento.')),
        (FEATURE_PRODUCT, _('Pago por producto.')),
        (FEATURE_ASICOINS, _('Pago por Asicoins.')),
    )

    owner = fields.ReferenceField('Account', reverse_delete_rule=CASCADE)
    transactions = fields.ListField(fields.ReferenceField('Transaction'),
        reverse_delete_rule=PULL)
    date = fields.DateTimeField()
    feature = fields.IntField(choices=FEATURE_CHOICES)
    item = fields.GenericReferenceField()

    @classmethod
    def make_bill(cls, item, **kwargs):
        from requesting.documents import Request

        data = {
            'date': dt.datetime.now(),
            'item': item,
        }

        if isinstance(item, Request):
            data.update({
                'feature': cls.FEATURE_REQUEST,
                'owner': item.client.account,
                'transactions': item.transactions,
            })
        else:
            raise ValueError

        return cls.objects.create(**data)

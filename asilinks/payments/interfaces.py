
from abc import ABCMeta, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
import paypalrestsdk

class BasePaymentInterface(metaclass=ABCMeta):

    @abstractmethod
    def calculate_payment_fee(self, *args, **kwargs):
        pass

    @abstractmethod
    def calculate_payout_fee(self, *args, **kwargs):
        pass

    @abstractmethod
    def generate_token(self, *args, **kwargs):
        pass

    @abstractmethod
    def make_payment(self, *args, **kwargs):
        pass

    @abstractmethod
    def make_refund(self, *args, **kwargs):
        pass

    @abstractmethod
    def make_payout(self, *args, **kwargs):
        pass


class BypassInterface(BasePaymentInterface):

    def calculate_payment_fee(self, *args, **kwargs):
        return Decimal('10.00')

    def calculate_payout_fee(self, *args, **kwargs):
        return Decimal('2.00')

    def generate_token(self, *args, **kwargs):
        return 'bypass'

    def make_payment(self, *args, **kwargs):
        return 'bypass'

    def make_refund(self, *args, **kwargs):
        return 'bypass'

    def make_payout(self, *args, **kwargs):
        return 'bypass'


class PaypalInterface(BasePaymentInterface):

    def calculate_payment_fee(self, amount, *args, **kwargs):
        fee_constants = settings.PAYMENT_CONSTANTS['paypal_fees']

        fee = ((amount * fee_constants['percent'] + fee_constants['flat'])
            / (1 - fee_constants['percent'])).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP)
        return fee

    def calculate_payout_fee(self, amount, *args, **kwargs):
        fee_constants = settings.PAYMENT_CONSTANTS['paypal_fees']

        fee = min(amount * fee_constants['payout_percent'],
            fee_constants['payout_max']).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP)
        return fee

    def generate_token(self, amount, **kwargs):
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"},
            "redirect_urls": {
                "return_url": "https://asilinks.com/payment/execute",
                "cancel_url": "https://asilinks.com"},
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": "requerimiento",
                        "sku": "item",
                        "price": str(amount),
                        "currency": "USD",
                        "quantity": 1}]},
                "amount": {
                    "total": str(amount),
                    "currency": "USD"},
                "description": "Pago por cuota de requerimiento."}]})

        if not payment.create():
            raise PaymentError(payment.error)

        return payment.id

    def make_payment(self, payment_id, payer_id, **kwargs):
        payment = paypalrestsdk.Payment.find(payment_id)

        if not payment.execute({"payer_id": payer_id}):
            raise PaymentError(payment.error)

        sale = payment.transactions[0].related_resources[0].sale
        return sale.id

    def make_refund(self, sale_id, amount, **kwargs):
        sale = paypalrestsdk.Sale.find(sale_id)

        refund = sale.refund({
            "amount": {
                "total":str(amount),
                "currency": "USD"}
        })

        if not refund.success():
            raise RefundError(refund.error)

        return refund.id

    def make_payout(self, receiver, amount, **kwargs):
        if receiver.paypal_email is None:
            raise PaypalEmailRequired

        payout = paypalrestsdk.Payout({
            "sender_batch_header": {
                # "sender_batch_id": "batch_1",
                "email_subject": "You have a payment from Asilinks Platform."
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": str(amount),
                        "currency": "usd"
                    },
                    "receiver": receiver.paypal_email,
                    "note": "Thank you, for use Asilinks.",
                    # "sender_item_id": "item_1"
                }
            ]
        })

        if not payout.create():
            raise PayoutError(payout.error)

        return payout.batch_header.payout_batch_id


class ContextInterfaceError(BaseException):
    def __init__(self, error):
        self.error = error


class PaypalEmailRequired(BaseException):
    pass


class PaymentError(BaseException):
    def __init__(self, error):
        self.error = error


class RefundError(BaseException):
    def __init__(self, error):
        self.error = error


class PayoutError(BaseException):
    def __init__(self, error):
        self.error = error


INTERFACES = {
    'bypass': BypassInterface,
    'paypal': PaypalInterface,
}

def get_interface(key:str) -> BasePaymentInterface:

    if key == 'bypass' and not settings.DEBUG:
        raise ContextInterfaceError('La intefaz bypass no está permitida en producción.')

    if key not in INTERFACES:
        raise ContextInterfaceError('La interfaz {} no está definida.'.format(key))

    return INTERFACES[key]()

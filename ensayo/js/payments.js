
var jwt_token;
var partner = '5bd056dc721c160332c059a8';
var request = '5be0026d721c16000f82054a';
$('#request-id').val(request);

var email = 'test5@asilinks.com';
var password = 'pass123';

$('#get-request').click(function() {
  console.log('Solicitando autenticación...');

  $.ajax({
    type: 'post',
    url: "/dev/token_auth/",
    dataType: "json",
    contentType: "application/json",
    data: JSON.stringify({ 'email': email, 'password': password }),
    success: function (data) {
      jwt_token = data['token'];
      console.log(data);
    },
    error: function (data) {
      console.log(data);
    },
  });

  paypal.Button.render({
    env: 'sandbox',
    payment: function() {
        return new paypal.Promise(function(resolve, reject) {
          body = {
            partner: partner,
            interface: 'paypal'
          }

          $.ajax({
            type: 'post',
            url: "/dev/requests/"+ $('#request-id').val() +"/payment_token/",
            dataType: "json",
            contentType: "application/json",
            beforeSend: function (xhr) {
              xhr.setRequestHeader ("Authorization", "JWT " + jwt_token);
            },
            data: JSON.stringify(body),
            success: function( data ) {
              console.log('Solicitando permiso de pago a paypal...');
              resolve(data['payment_token']);
            },
            error: function( data ) {
              console.log(data);
            },
          });
        });
    },

    onAuthorize: function(data) {
      // Call payment execute (see step 5)
      console.log('onAuthorize: ');
      console.log(data);
      body = {
        partner: partner,
        interface: 'paypal',
        'payment_id': data['paymentID'],
        'payer_id': data['payerID'],
      }

      $.ajax({
        type: 'post',
        url: "/dev/requests/"+ $('#request-id').val() +"/accept_offer/",
        dataType: "json",
        contentType: "application/json",
        beforeSend: function (xhr) {
          xhr.setRequestHeader ("Authorization", "JWT " + jwt_token);
        },
        data: JSON.stringify(body),
        success: function( data ) {
          console.log('Solicitando permiso de pago a paypal...');
          console.log(data);
        },
        error: function( data ) {
          console.log(data);
        },
      });
    }

  }, '#paypal-button');
});

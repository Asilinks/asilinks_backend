
var config = {
    apiKey: "AIzaSyDpkWLF4gjH5vwwcxLRYrQQYTE-Kg5kImA",
    authDomain: "asilinks-74c4b.firebaseapp.com",
    databaseURL: "https://asilinks-74c4b.firebaseio.com",
    projectId: "asilinks-74c4b",
    storageBucket: "asilinks-74c4b.appspot.com",
    messagingSenderId: "895441371703"
};

var email = 'test5@asilinks.com';
var password = 'pass123';

firebase.initializeApp(config);


const messaging = firebase.messaging();

// pidiendo permisos para las notificaciones...
messaging.requestPermission()
    .then(function() {
      console.log('Notification permission granted.');
      // TODO(developer): Retrieve an Instance ID token for use with FCM.
      // ...
    })
    .catch(function(err) {
      console.log('Unable to get permission to notify.', err);
    });


messaging.getToken()
  .then(function(currentToken) {
    if (currentToken) {
        console.log(currentToken);
        sendTokenToServer(currentToken);
        // updateUIForPushEnabled(currentToken);
    } else {
        // Show permission request.
        console.log('No Instance ID token available. Request permission to generate one.');
        // Show permission UI.
        updateUIForPushPermissionRequired();
        setTokenSentToServer(false);
    }
  })
  .catch(function(err) {
        console.log('An error occurred while retrieving token. ', err);
        // showToken('Error retrieving Instance ID token. ', err);
        setTokenSentToServer(false);
  });

messaging.onMessage(function(payload) {
  console.log("Message received. ", payload);
  // ...
});


function sendTokenToServer(registration_id){
  $.ajax({
    type: 'post',
    url: "/dev/token_auth/",
    dataType: "json",
    contentType: "application/json",
    data: JSON.stringify({ 'email': email, 'password': password }),
    success: function (data) {
      jwt_token = data['token'];

      $.ajax({
        type: 'post',
        url: "/dev/self/devices/",
        dataType: "json",
        contentType: "application/json",
        beforeSend: function (xhr) {
          xhr.setRequestHeader("Authorization", "JWT " + jwt_token);
        },
        data: JSON.stringify({ 'registration_id': registration_id, 'type':'web'}),
        success: function (data) {
          console.log('Enviado registro de dispositivo.');
          console.log(data);

        },
        error: function (data) {
          console.log(data);
        },
      });
    },
    error: function (data) {
      console.log(data);
    },
  });
}
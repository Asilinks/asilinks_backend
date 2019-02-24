// Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here, other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/5.3.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/5.3.1/firebase-messaging.js');

// Initialize the Firebase app in the service worker by passing in the
// messagingSenderId.
firebase.initializeApp({
    apiKey: "AIzaSyDpkWLF4gjH5vwwcxLRYrQQYTE-Kg5kImA",
    authDomain: "asilinks-74c4b.firebaseapp.com",
    databaseURL: "https://asilinks-74c4b.firebaseio.com",
    projectId: "asilinks-74c4b",
    storageBucket: "asilinks-74c4b.appspot.com",
    messagingSenderId: "895441371703"
});

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();

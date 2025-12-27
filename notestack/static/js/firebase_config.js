
const firebaseConfig = {
    apiKey: "AIzaSyA8OOORKyKB-DoCLbbmsoY8MrbChh6AcpI",
    authDomain: "notestack-d14e7.firebaseapp.com",
    projectId: "notestack-d14e7",
    storageBucket: "notestack-d14e7.firebasestorage.app",
    messagingSenderId: "720277805120",
    appId: "1:720277805120:web:5141c4cb5bec45a554a7a5",
    measurementId: "G-LLV8Z7LT94"
};

if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
} else {
    firebase.app();
}
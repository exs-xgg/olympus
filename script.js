document.getElementById('login-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    // Simple form validation
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (username === '' || password === '') {
        alert('Please fill in both fields.');
    } else {
        alert('Form submitted successfully!');
        // Here you can add code to handle the form submission, e.g., sending data to a server
    }
});
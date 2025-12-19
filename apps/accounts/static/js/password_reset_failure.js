document.addEventListener('DOMContentLoaded', function() {
    let countdown = 10;
    const countdownElement = document.getElementById('countdown-number');

    if (!countdownElement) {
        console.error('Countdown element not found');
        return;
    }

    countdownElement.textContent = countdown;
    
    const countdownInterval = setInterval(() => {
        countdown--;
        countdownElement.textContent = countdown;
        
        if (countdown <= 0) {
            clearInterval(countdownInterval);
            // Redirect to home page
            window.location.href = '/';
        }
    }, 1000); // Update every second
});
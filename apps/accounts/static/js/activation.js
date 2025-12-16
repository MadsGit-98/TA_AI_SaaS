// Auto-submit the activation form when the page loads
document.addEventListener('DOMContentLoaded', function() {
    const activationForm = document.getElementById('activationForm');
    if (activationForm) {
        activationForm.submit();
    }
});
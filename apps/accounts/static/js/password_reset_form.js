document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('passwordResetForm');

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Clear previous errors
            document.getElementById('password-error').classList.add('hidden');
            document.getElementById('confirm-password-error').classList.add('hidden');
            document.getElementById('general-error').classList.add('hidden');

            const newPassword = document.getElementById('new_password').value;
            const confirmPassword = document.getElementById('confirm_password').value;

            // Get UID and token from the hidden form fields
            //const uid = document.querySelector('input[name="uid"]').value;
            const uid = document.getElementById('user_id').value;
            const token = document.getElementById('password_reset_token').value;
            //const token = document.querySelector('input[name="token"]').value;

            if (newPassword !== confirmPassword) {
                document.getElementById('confirm-password-error').textContent = 'Passwords do not match';
                document.getElementById('confirm-password-error').classList.remove('hidden');
                return;
            }

            try {
                const response = await fetch(`/api/accounts/auth/password/reset/update/${uid}/${token}/`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        new_password: newPassword,
                        confirm_password: confirmPassword,
                        token: token  // Include token in the request body as well
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    // Show success message
                    document.getElementById('passwordResetForm').classList.add('hidden');
                    document.getElementById('success-message').classList.remove('hidden');

                    // Redirect to login after a delay
                    setTimeout(() => {
                        // Validate redirect URL is relative or to trusted domain
                        const redirectUrl = data.redirect_url;
                        if (redirectUrl && (redirectUrl.startsWith('/') || redirectUrl.startsWith(window.location.origin))) {
                            window.location.href = redirectUrl;
                        } else {
                            // Fallback to default login page
                            window.location.href = '/accounts/login/';
                        }
                    }, 2000);                } else {
                    // Display errors
                    if (data.error) {
                        document.getElementById('general-error').textContent = data.error;
                        document.getElementById('general-error').classList.remove('hidden');
                    }
                    if (data.new_password) {
                        const errorMsg = Array.isArray(data.new_password) ? data.new_password[0] : data.new_password;
                        document.getElementById('password-error').textContent = errorMsg;
                        document.getElementById('password-error').classList.remove('hidden');
                    }
                    if (data.confirm_password) {
                        const errorMsg = Array.isArray(data.confirm_password) ? data.confirm_password[0] : data.confirm_password;
                        document.getElementById('confirm-password-error').textContent = errorMsg;
                        document.getElementById('confirm-password-error').classList.remove('hidden');
                    }
                }
            } catch (error) {
                document.getElementById('general-error').textContent = 'An error occurred. Please try again.';
                document.getElementById('general-error').classList.remove('hidden');
            }
        });
    }
});
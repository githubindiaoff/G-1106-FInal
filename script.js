document.addEventListener('DOMContentLoaded', () => {
    // Tab switching elements
    const tabSignIn = document.getElementById('tabSignIn');
    const tabSignUp = document.getElementById('tabSignUp');
    const tabsContainer = document.querySelector('.tabs');
    const signInForm = document.getElementById('signInForm');
    const signUpForm = document.getElementById('signUpForm');
    const linkToSignUp = document.getElementById('linkToSignUp');
    const linkToSignIn = document.getElementById('linkToSignIn');

    // Switch to Sign Up
    const goSignUp = (e) => {
        if(e) e.preventDefault();
        tabsContainer.setAttribute('data-active', 'signup');
        tabSignUp.classList.add('active');
        tabSignIn.classList.remove('active');
        
        signInForm.classList.remove('active');
        // Slight delay to allow CSS transitions to feel smoother
        setTimeout(() => signUpForm.classList.add('active'), 50);
    };

    // Switch to Sign In
    const goSignIn = (e) => {
        if(e) e.preventDefault();
        tabsContainer.removeAttribute('data-active');
        tabSignIn.classList.add('active');
        tabSignUp.classList.remove('active');
        
        signUpForm.classList.remove('active');
        setTimeout(() => signInForm.classList.add('active'), 50);
    };

    // Event Listeners for tabs
    tabSignUp.addEventListener('click', goSignUp);
    tabSignIn.addEventListener('click', goSignIn);
    linkToSignUp.addEventListener('click', goSignUp);
    linkToSignIn.addEventListener('click', goSignIn);

    // Validation Functions
    const isValidMobile = (num) => /^[0-9]{10}$/.test(num);
    const isValidPassword = (pwd) => pwd.length >= 6;

    // Remove errors on input
    const inputs = document.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            input.setCustomValidity(''); // clear browser native
            const errorElementId = input.id + '-err';
            const errSpan = document.getElementById(errorElementId);
            if (errSpan) errSpan.textContent = '';
            
            // Revalidate confirm password if either password changes dynamically
            if(input.id === 'su-confirm-password' || input.id === 'su-password') {
                const suErr = document.getElementById('su-confirm-err');
                if(suErr) suErr.textContent = '';
            }
        });
    });

    // Handle Sign In Submit
    signInForm.addEventListener('submit', (e) => {
        e.preventDefault();
        let valid = true;
        
        const mobile = document.getElementById('si-mobile').value.trim();
        const pwd = document.getElementById('si-password').value;

        if (!isValidMobile(mobile)) {
            document.getElementById('si-mobile-err').textContent = 'Please enter a valid 10-digit mobile number';
            valid = false;
        }

        if (!isValidPassword(pwd)) {
            document.getElementById('si-password-err').textContent = 'Password must be at least 6 characters long';
            valid = false;
        }

        if (valid) {
            // Assume API call succeeds
            window.location.href = 'prediction.html';
        }
    });

    // Handle Sign Up Submit
    signUpForm.addEventListener('submit', (e) => {
        e.preventDefault();
        let valid = true;

        const mobile = document.getElementById('su-mobile').value.trim();
        const pwd = document.getElementById('su-password').value;
        const confirmPwd = document.getElementById('su-confirm-password').value;

        if (!isValidMobile(mobile)) {
            document.getElementById('su-mobile-err').textContent = 'Please enter a valid 10-digit mobile number';
            valid = false;
        }

        if (!isValidPassword(pwd)) {
            document.getElementById('su-password-err').textContent = 'Password must be at least 6 characters long';
            valid = false;
        }

        if (pwd !== confirmPwd) {
            document.getElementById('su-confirm-err').textContent = 'Passwords do not match';
            valid = false;
        }

        if (valid) {
            // Assume API call succeeds
            alert('Successfully Registered account for NutriDetector!');
            signUpForm.reset();
            goSignIn();
        }
    });
});

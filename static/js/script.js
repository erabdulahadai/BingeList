document.addEventListener('DOMContentLoaded', () => {
    // Add a subtle scanline effect to images on load
    const images = document.querySelectorAll('img');
    images.forEach(img => {
        img.style.opacity = '0';
        img.onload = () => {
            img.style.transition = 'opacity 1s ease-in-out';
            img.style.opacity = '1';
        };
    });

    // Handle Button Clicks for "Add" feedback
    const addButtons = document.querySelectorAll('.btn-neon');
    addButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            if(this.innerText === '+ Add') {
                this.style.boxShadow = '0 0 30px var(--neon)';
                this.innerText = 'Syncing...';
            }
        });
    });
});
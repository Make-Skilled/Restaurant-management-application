// File upload preview functionality
function previewImage(input, previewElement) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const preview = document.getElementById(previewElement);
            preview.src = e.target.result;
            preview.classList.remove('hidden');
        }
        
        reader.readAsDataURL(input.files[0]);
    }
}

// Drag and drop functionality for upload zones
function initializeUploadZone(uploadZoneId, inputId) {
    const uploadZone = document.getElementById(uploadZoneId);
    const input = document.getElementById(inputId);
    
    if (!uploadZone || !input) return;
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight(e) {
        uploadZone.classList.add('border-orange-500', 'bg-orange-50');
    }
    
    function unhighlight(e) {
        uploadZone.classList.remove('border-orange-500', 'bg-orange-50');
    }
    
    uploadZone.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        input.files = files;
        
        // Trigger change event
        const event = new Event('change');
        input.dispatchEvent(event);
    }
}

// Gallery image modal functionality
function initializeGalleryModal() {
    const modal = document.getElementById('gallery-modal');
    const modalImage = document.getElementById('modal-image');
    const modalCaption = document.getElementById('modal-caption');
    const closeModal = document.getElementById('close-modal');
    
    if (!modal || !modalImage || !modalCaption || !closeModal) return;
    
    // Open modal
    document.querySelectorAll('.gallery-item').forEach(item => {
        item.addEventListener('click', () => {
            const img = item.querySelector('img');
            const caption = item.dataset.caption;
            
            modalImage.src = img.src;
            modalCaption.textContent = caption;
            modal.classList.remove('hidden');
        });
    });
    
    // Close modal
    closeModal.addEventListener('click', () => {
        modal.classList.add('hidden');
    });
    
    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.classList.add('hidden');
        }
    });
}

// Image lazy loading
function initializeLazyLoading() {
    const lazyImages = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });
    
    lazyImages.forEach(img => imageObserver.observe(img));
}

// Initialize all image-related functionality
document.addEventListener('DOMContentLoaded', () => {
    // Initialize upload zones if they exist
    initializeUploadZone('menu-image-upload', 'menu-image-input');
    initializeUploadZone('gallery-image-upload', 'gallery-image-input');
    
    // Initialize gallery modal if on gallery page
    if (document.querySelector('.gallery-item')) {
        initializeGalleryModal();
    }
    
    // Initialize lazy loading
    initializeLazyLoading();
});

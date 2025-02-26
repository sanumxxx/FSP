document.addEventListener('DOMContentLoaded', function() {
    // Обработка подтверждения удаления
    const deleteButtons = document.querySelectorAll('[data-delete-id]');

    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите удалить этот элемент?')) {
                e.preventDefault();
            }
        });
    });

    // Предпросмотр загружаемых изображений
    const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');

    imageInputs.forEach(input => {
        input.addEventListener('change', function() {
            const previewContainer = document.getElementById(this.id + '_preview');
            if (!previewContainer) return;

            previewContainer.innerHTML = '';

            if (this.files && this.files[0]) {
                const reader = new FileReader();

                reader.onload = function(e) {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.classList.add('img-thumbnail', 'mt-2');
                    img.style.maxHeight = '200px';
                    previewContainer.appendChild(img);
                };

                reader.readAsDataURL(this.files[0]);
            }
        });
    });

    // Инициализация всплывающих подсказок
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
});
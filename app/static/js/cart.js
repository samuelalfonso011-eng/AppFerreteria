// Manejo asíncrono del carrito de compras
document.addEventListener('DOMContentLoaded', () => {
    // Interceptar botones de agregar al carrito con clase '.async-add-cart'
    const addCartButtons = document.querySelectorAll('.async-add-cart');
    addCartButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const productId = btn.dataset.productId;
            const quantityInput = document.getElementById(`qty-${productId}`);
            const quantity = quantityInput ? parseInt(quantityInput.value, 10) : 1;
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

            btn.disabled = true;
            const originalText = btn.innerHTML;
            btn.innerHTML = 'Agregando...';

            try {
                const response = await fetch('/carrito/agregar', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ''
                    },
                    body: JSON.stringify({
                        product_id: productId,
                        quantity: quantity
                    })
                });

                const data = await response.json();
                if (data.success) {
                    showToast(data.message, 'success');
                    // Actualizar badge del carrito en el navbar
                    const badge = document.querySelector('.cart-badge');
                    if (badge) {
                        badge.textContent = data.cart.total_items;
                    }
                } else {
                    showToast(data.message, 'warning');
                }
            } catch (error) {
                showToast('Error al comunicar con el servidor.', 'danger');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    });
});

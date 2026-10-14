"""
Diccionario y utilidades de internacionalización para la tienda (Español / Inglés).
Permite traducir dinámicamente etiquetas del navbar, footer, botones e interfaz de usuario.
"""

TRANSLATIONS = {
    'es': {
        'catalog': 'Catálogo',
        'delivery': 'Entregas',
        'about': 'Nosotros',
        'contact': 'Contacto',
        'my_orders': 'Mis Pedidos',
        'login': 'Ingresar',
        'register': 'Registrarse',
        'logout': 'Salir',
        'cart': 'Carrito',
        'search_placeholder': 'Buscar herramientas, materiales o SKU...',
        'admin_mode': '⚙️ Modo Admin',
        'materials_tools': 'Materiales & Herramientas',
        'customer_service': 'Atención al Cliente',
        'dispatch_hours': 'Horarios de Despacho',
        'legal_privacy': 'Legal & Privacidad',
        'privacy_policy': 'Política de Privacidad',
        'terms_conditions': 'Términos y Condiciones',
        'cookies_policy': 'Política de Cookies',
        'quick_links': 'Enlaces Rápidos',
        'all_rights_reserved': 'Todos los derechos reservados. Desarrollado con Flask y PostgreSQL.',
        'add_to_cart': 'Agregar al carrito',
        'out_of_stock': 'Agotado',
        'available': 'Disponible',
        'price': 'Precio',
        'total': 'Total',
        'subtotal': 'Subtotal',
        'checkout': 'Finalizar Compra',
        'back_to_top': 'Volver arriba',
        'featured_products': 'Productos Destacados',
        'new_arrivals': 'Novedades',
        'featured_categories': 'Categorías Destacadas',
        'whatsapp_support': 'Asesoría por WhatsApp'
    },
    'en': {
        'catalog': 'Catalog',
        'delivery': 'Deliveries',
        'about': 'About Us',
        'contact': 'Contact',
        'my_orders': 'My Orders',
        'login': 'Sign In',
        'register': 'Register',
        'logout': 'Sign Out',
        'cart': 'Cart',
        'search_placeholder': 'Search tools, materials or SKU...',
        'admin_mode': '⚙️ Admin Mode',
        'materials_tools': 'Hardware & Materials',
        'customer_service': 'Customer Support',
        'dispatch_hours': 'Dispatch Hours',
        'legal_privacy': 'Legal & Privacy',
        'privacy_policy': 'Privacy Policy',
        'terms_conditions': 'Terms & Conditions',
        'cookies_policy': 'Cookies Policy',
        'quick_links': 'Quick Links',
        'all_rights_reserved': 'All rights reserved. Powered by Flask and PostgreSQL.',
        'add_to_cart': 'Add to Cart',
        'out_of_stock': 'Out of Stock',
        'available': 'In Stock',
        'price': 'Price',
        'total': 'Total',
        'subtotal': 'Subtotal',
        'checkout': 'Checkout',
        'back_to_top': 'Back to top',
        'featured_products': 'Featured Products',
        'new_arrivals': 'New Arrivals',
        'featured_categories': 'Featured Categories',
        'whatsapp_support': 'WhatsApp Support'
    }
}


def translate(key: str, lang: str = 'es', default: str = None) -> str:
    """Retorna la traducción para la clave solicitada en el idioma actual."""
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS['es'])
    return lang_dict.get(key, default or key)

import os
from flask import current_app


class ImageService:
    """Servicio para validación, saneamiento y almacenamiento seguro de imágenes locales."""

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

    @classmethod
    def allowed_file(cls, filename: str) -> bool:
        """Verifica si la extensión del archivo está permitida."""
        if not filename or '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in cls.ALLOWED_EXTENSIONS

    @classmethod
    def save_product_image(cls, file_storage) -> str:
        """
        Valida rigurosamente la imagen, la optimiza con Pillow (máx 1200px con LANCZOS,
        elimina EXIF, comprime en WebP/JPEG) y la guarda de forma segura.
        """
        from app.utils.image_optimizer import save_optimized_image
        return save_optimized_image(file_storage, quality=80)

    @classmethod
    def delete_product_image(cls, filename: str) -> bool:
        """Elimina una imagen del disco local de forma segura."""
        if not filename:
            return False
        
        # Prevenir directory traversal
        clean_name = os.path.basename(filename)
        upload_dir = current_app.config['UPLOAD_FOLDER']
        full_path = os.path.join(upload_dir, clean_name)

        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                current_app.logger.exception("No fue posible eliminar la imagen del producto")
                return False
        return False

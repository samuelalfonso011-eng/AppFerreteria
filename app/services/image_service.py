import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename
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
        Valida rigurosamente la imagen y la guarda con un nombre UUID único en el servidor local.
        Retorna el nombre del archivo guardado (ej. 'a1b2c3d4.webp').
        """
        if not file_storage or not file_storage.filename:
            raise ValueError("No se ha seleccionado ningún archivo de imagen.")

        if not cls.allowed_file(file_storage.filename):
            raise ValueError(f"Formato no permitido. Solo se aceptan: {', '.join(cls.ALLOWED_EXTENSIONS).upper()}.")

        # Verificar tamaño
        file_storage.seek(0, os.SEEK_END)
        size = file_storage.tell()
        file_storage.seek(0)
        if size > cls.MAX_FILE_SIZE:
            raise ValueError("La imagen supera el tamaño máximo permitido de 5 MB.")

        # Verificar integridad real del archivo con Pillow (evita ejecutables o archivos corruptos)
        try:
            image = Image.open(file_storage)
            image.verify()  # Verifica que sea un archivo de imagen real
            file_storage.seek(0)  # Resetear puntero tras la verificación
        except Exception:
            raise ValueError("El archivo subido no es una imagen válida o está dañado.")

        # Generar nombre único seguro
        raw_filename = secure_filename(file_storage.filename)
        ext = raw_filename.rsplit('.', 1)[1].lower() if '.' in raw_filename else 'webp'
        if ext == 'jpeg':
            ext = 'jpg'
        unique_name = f"{uuid.uuid4().hex}.{ext}"

        # Directorio de destino
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        dest_path = os.path.join(upload_dir, unique_name)

        # Reabrir y guardar para normalizar
        img_to_save = Image.open(file_storage)
        # Convertir imágenes RGBA a RGB si se guardan como JPEG
        if ext in ['jpg', 'jpeg'] and img_to_save.mode in ('RGBA', 'P'):
            img_to_save = img_to_save.convert('RGB')
        img_to_save.save(dest_path, optimize=True, quality=85)

        return unique_name

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
                return False
        return False

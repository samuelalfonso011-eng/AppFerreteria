import os
import uuid
import logging
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
from flask import current_app

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1200
DEFAULT_QUALITY = 80
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_FORMATS = {'PNG', 'JPEG', 'WEBP'}  # formato real detectado por Pillow
MAX_PIXELS = 40_000_000  # ~40 MP: evita "decompression bombs" (5 MB comprimidos pueden expandirse a GBs)
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def optimize_image(image: Image.Image, max_dim: int = MAX_DIMENSION) -> Image.Image:
    """
    Normaliza la orientación según EXIF, remueve metadatos innecesarios y
    redimensiona proporcionalmente usando Image.Resampling.LANCZOS si supera max_dim.
    """
    # 1. Normalizar orientación EXIF (evita fotos volteadas en móviles)
    try:
        image = ImageOps.exif_transpose(image)
    except (OSError, SyntaxError, ValueError):
        logger.warning("Metadatos EXIF inválidos; se conserva la orientación original")

    # 2. Redimensionar proporcionalmente con filtro Lanczos de alta fidelidad
    width, height = image.size
    if width > max_dim or height > max_dim:
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        logger.debug(f"[PILLOW] Imagen redimensionada de {width}x{height} a {image.size[0]}x{image.size[1]}")

    return image


def save_optimized_image(file_storage, upload_folder: str = None, target_format: str = 'webp', quality: int = DEFAULT_QUALITY) -> str:
    """
    Pipeline de compresión y optimización de imágenes con Pillow:
    - Valida firma binaria real del archivo.
    - Redimensiona proporcionalmente a un máximo de 1200px con LANCZOS.
    - Elimina metadatos EXIF.
    - Comprime en WebP o JPEG progresivo con quality=80 y optimize=True.
    - Retorna el nombre único del archivo guardado.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No se ha seleccionado ningún archivo de imagen.")

    # Validar extensión básica
    filename_raw = secure_filename(file_storage.filename)
    if '.' not in filename_raw:
        raise ValueError("El archivo no tiene una extensión válida.")
    raw_ext = filename_raw.rsplit('.', 1)[1].lower()
    if raw_ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Formato no permitido. Solo se aceptan: {', '.join(ALLOWED_EXTENSIONS).upper()}.")

    # Validar tamaño del archivo
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_FILE_SIZE:
        raise ValueError("La imagen supera el tamaño máximo permitido de 5 MB.")

    # Validar firma binaria real con Pillow (el formato detectado manda, no la extensión declarada)
    try:
        verify_img = Image.open(file_storage)
        detected_format = verify_img.format
        verify_img.verify()
        file_storage.seek(0)
    except Image.DecompressionBombError:
        raise ValueError("La imagen tiene dimensiones excesivas y fue rechazada.")
    except Exception:
        raise ValueError("El archivo subido no es una imagen válida o está dañado.")

    if detected_format not in ALLOWED_FORMATS:
        raise ValueError("El contenido del archivo no corresponde a una imagen PNG, JPEG o WEBP.")

    # Reabrir para procesamiento tras la verificación binaria
    try:
        img = Image.open(file_storage)
        if img.width * img.height > MAX_PIXELS:
            raise ValueError("La imagen tiene dimensiones excesivas y fue rechazada.")
        img = optimize_image(img, max_dim=MAX_DIMENSION)
    except Image.DecompressionBombError:
        raise ValueError("La imagen tiene dimensiones excesivas y fue rechazada.")
    except (OSError, SyntaxError):
        raise ValueError("El archivo subido no es una imagen válida o está dañado.")

    # Determinar formato óptimo
    fmt = target_format.lower().replace('.', '')
    if fmt == 'webp':
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
        save_format = 'WEBP'
        save_params = {'quality': quality, 'optimize': True, 'method': 4}
        final_ext = 'webp'
    elif fmt in ['jpg', 'jpeg']:
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        save_format = 'JPEG'
        save_params = {'quality': quality, 'optimize': True, 'progressive': True}
        final_ext = 'jpg'
    else:
        save_format = 'PNG'
        save_params = {'optimize': True}
        final_ext = 'png'

    # Directorio de destino
    dest_dir = upload_folder or current_app.config['UPLOAD_FOLDER']
    os.makedirs(dest_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}.{final_ext}"
    dest_path = os.path.join(dest_dir, unique_filename)

    img.save(dest_path, format=save_format, **save_params)
    logger.info(f"[PILLOW] Imagen guardada optimizada: {unique_filename} ({save_format}, calidad {quality}%)")

    return unique_filename


# Alias para compatibilidad con suites de pruebas y servicios
optimize_product_image = save_optimized_image


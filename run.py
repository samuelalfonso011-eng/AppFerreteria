import os
from app import create_app, db

app = create_app()

if __name__ == '__main__':
    # Ejecución local obligatoria en el puerto 5000
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    is_dev = os.getenv('FLASK_ENV', 'development').lower() == 'development'

    print(f"\n=======================================================")
    print(f" FERRETERÍA WEB INICIADA EXITOSAMENTE")
    print(f" Servidor disponible en: http://{host}:{port}")
    print(f" Entorno: {'Desarrollo (Debug Activo)' if is_dev else 'Producción'}")
    print(f" Para detener el servidor presiona CTRL + C")
    print(f"=======================================================\n")

    app.run(host=host, port=port, debug=is_dev)

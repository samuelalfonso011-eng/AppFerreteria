from app.extensions import db


class CacheVersion(db.Model):
    """Token compartido por todos los procesos: si cambia, toda cache derivada queda obsoleta.

    Cada worker guarda su cache en memoria, pero las claves llevan este token. Una escritura
    en cualquier worker lo reemplaza en la misma transaccion, asi ningun otro worker puede
    servir precios o stock anteriores al commit.
    """
    __tablename__ = "cache_versions"

    scope = db.Column(db.String(30), primary_key=True)
    token = db.Column(db.String(32), nullable=False)

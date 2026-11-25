class BusinessError(Exception):
    """Error de negocio con codigo estable y mensaje listo para mostrar al usuario."""
    status = 409
    code = "conflict"

    def __init__(self, message, code=None, status=None, **extra):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.extra = extra

    def to_dict(self):
        return {"error": self.code, "message": self.message, **self.extra}


class InsufficientStockError(BusinessError):
    code = "stock"

    def __init__(self, product, requested, available):
        if available > 0:
            message = f"Solo quedan {available} unidades de {product.name}. Ajusta la cantidad para continuar."
        else:
            message = f"{product.name} se agotó mientras comprabas. Retíralo del carrito para continuar."
        super().__init__(message, product_id=product.id, requested=requested, available=available)

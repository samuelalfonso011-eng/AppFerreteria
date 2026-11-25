from flask import jsonify


def json_error(status, code, message, **extra):
    response = jsonify(error=code, message=message, **extra)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def no_store(response, status=None):
    if status is not None:
        response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response

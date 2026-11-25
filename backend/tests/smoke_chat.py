"""Comprueba POST /api/chat por HTTP usando la cookie y el token CSRF."""

import argparse
import json
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--expect", choices=("ai", "fallback"), required=True)
    parser.add_argument("--message", default="¿Qué taladros tienen y cuál es su precio?")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    with client.open(base + "/api/auth/csrf", timeout=10) as response:
        csrf = json.load(response)["csrf"]
    request = Request(
        base + "/api/chat",
        data=json.dumps({"message": args.message}).encode(),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
        method="POST",
    )
    with client.open(request, timeout=15) as response:
        result = json.load(response)
    if (result.get("mode") != args.expect or not result.get("reply")
            or not isinstance(result.get("suggested_products"), list)):
        parser.exit(1, f"Se esperaba mode={args.expect} con una respuesta válida. Llegó {result!r}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

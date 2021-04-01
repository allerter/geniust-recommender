from json.decoder import JSONDecodeError
from typing import Awaitable, Callable, List, Tuple, Union
from urllib.parse import parse_qs

import jwt
from fastapi.responses import JSONResponse
from ratelimit import RateLimitMiddleware
from ratelimit.types import Scope


class EmptyInformation(Exception):  # noqa: B903
    def __init__(self, scope: Scope, message: str = "") -> None:
        self.scope = scope
        self.message = message


class BadInformation(Exception):  # noqa: B903
    def __init__(self, scope: Scope, message: str = "") -> None:
        self.scope = scope
        self.message = message


class CustomRateLimitMiddleware(RateLimitMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        except (BadInformation, EmptyInformation) as e:
            response = JSONResponse(
                status_code=401,
                content={"detail": e.args[1]},
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)


def create_jwt_auth(
    key: str,
    algorithms: Union[List[str], str],
) -> Callable[[Scope], Awaitable[Tuple[str, str]]]:
    """JWT Authentication

    from https://github.com/abersheeran/
    asgi-ratelimit/blob/master/ratelimit/auths/jwt.py
    """

    async def jwt_auth(scope: Scope) -> Tuple[str, str]:
        """
        About jwt header, read this link:
        """
        for name, value in scope["headers"]:  # type: bytes, bytes
            if name == b"authorization":
                try:
                    authorization = value.decode("utf8")
                except JSONDecodeError:  # pragma: no cover
                    raise BadInformation(scope, "Invalid token")
                break
        else:
            parameters = parse_qs(scope["query_string"])
            token = parameters.get(b"access_token")
            if token is None:
                raise EmptyInformation(scope, "Unauthorized access")
            authorization = f"Bearer {token[0].decode('utf8')}"

        bad_header = False
        try:
            token_type, json_web_token = authorization.split(" ")
        except ValueError:
            bad_header = True

        if bad_header or token_type != "Bearer":
            raise BadInformation(
                scope,
                "Authorization header must be `Bearer` type. Like: `Bearer token`",
            )

        try:
            data = jwt.decode(json_web_token, key, algorithms=algorithms)
        except jwt.InvalidTokenError:
            raise BadInformation(scope, "Invalid token")

        try:
            return data["user"], data.get("group", "default")
        except KeyError:
            raise BadInformation(scope, "Invalid token")

    return jwt_auth

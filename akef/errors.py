
class AkefError(Exception):
    def __init__(self, message: str = "", code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class NetworkError(AkefError):
    pass


class AuthError(AkefError):
    pass


class APIError(AkefError):
    pass


class NoRoleError(AkefError):
    pass


class AlreadyCheckedIn(APIError):
    pass


class UnknownCharacter(AkefError):
    pass


class GameDataError(AkefError):
    pass


class MissingGameData(GameDataError):
    def __init__(self, kind: str, name):
        super().__init__(f"no {kind} {name!r} in Enka's data yet, try again after Enka updates")
        self.kind = kind
        self.name = name


class PlayerNotFound(AkefError):
    pass


class ShowcaseEmpty(AkefError):
    pass

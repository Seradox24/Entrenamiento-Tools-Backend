from dataclasses import dataclass

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .services import resolve_experience_token, resolve_launcher_access_token


@dataclass(frozen=True)
class IdentityPrincipal:
    moodle_user: object
    credential_type: str

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def username(self):
        return self.moodle_user.username


class BearerTokenAuthentication(BaseAuthentication):
    expected_prefix = ""

    def resolve_token(self, raw_token):
        raise NotImplementedError

    def authenticate(self, request):
        authorization = get_authorization_header(request).split()
        if not authorization:
            return None
        if len(authorization) != 2 or authorization[0].lower() != b"bearer":
            raise AuthenticationFailed("Encabezado Bearer invalido.")

        try:
            raw_token = authorization[1].decode("ascii")
        except UnicodeDecodeError as error:
            raise AuthenticationFailed("Token Bearer invalido.") from error
        if not raw_token.startswith(self.expected_prefix):
            raise AuthenticationFailed("Token Bearer invalido.")

        credential = self.resolve_token(raw_token)
        if credential is None:
            raise AuthenticationFailed("Token vencido, revocado o invalido.")
        return self.build_authentication_result(credential)

    def authenticate_header(self, request):
        return "Bearer"


class LauncherAccessAuthentication(BearerTokenAuthentication):
    expected_prefix = "som_la_"

    def resolve_token(self, raw_token):
        return resolve_launcher_access_token(raw_token)

    def build_authentication_result(self, access_token):
        moodle_user = access_token.launcher_session.moodle_user
        return (
            IdentityPrincipal(moodle_user, "launcher"),
            access_token,
        )


class ExperienceTokenAuthentication(BearerTokenAuthentication):
    expected_prefix = "som_xapi_"

    def resolve_token(self, raw_token):
        return resolve_experience_token(raw_token)

    def build_authentication_result(self, experience_launch):
        return (
            IdentityPrincipal(experience_launch.moodle_user, "experience"),
            experience_launch,
        )

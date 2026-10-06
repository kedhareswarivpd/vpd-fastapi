"""OAuth 2.0 / OIDC provider registry for social login.

Adding a new provider is a config-only change: add its client_id/secret/
redirect_uri to `Settings` (core/config.py), add its endpoint URLs and scope
here, and teach `routers/oauth.py::_extract_identity` how to read its
userinfo response shape. No other code needs to change — the login/callback
routes are provider-agnostic.

A provider is considered "configured" only when its client_id, client_secret,
and redirect_uri are all non-empty — `get_provider()` returns None otherwise,
which routers/oauth.py treats as 404 (that provider doesn't exist as far as
any caller can tell), independent of the global `settings.oauth_enabled`
switch. This means partial configuration (e.g. Google only, GitHub unset) is
safe and requires no code change to support.
"""
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str


def get_provider(name: str) -> OAuthProviderConfig | None:
    if name == "google":
        if not (settings.oauth_google_client_id and settings.oauth_google_client_secret and settings.oauth_google_redirect_uri):
            return None
        return OAuthProviderConfig(
            name="google",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v3/userinfo",
            client_id=settings.oauth_google_client_id,
            client_secret=settings.oauth_google_client_secret,
            redirect_uri=settings.oauth_google_redirect_uri,
            scope="openid email profile",
        )
    if name == "github":
        if not (settings.oauth_github_client_id and settings.oauth_github_client_secret and settings.oauth_github_redirect_uri):
            return None
        return OAuthProviderConfig(
            name="github",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            client_id=settings.oauth_github_client_id,
            client_secret=settings.oauth_github_client_secret,
            redirect_uri=settings.oauth_github_redirect_uri,
            scope="read:user user:email",
        )
    return None

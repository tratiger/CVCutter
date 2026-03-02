"""OAuth2 authentication helpers for YouTube API adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cvcutter.domain.services.credential_store import CredentialStore

try:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials as GoogleCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:  # pragma: no cover - dependency availability is runtime-environment specific.
    GoogleRequest = None  # type: ignore[assignment]
    GoogleCredentials = None  # type: ignore[assignment]
    InstalledAppFlow = None  # type: ignore[assignment]


class YouTubeAuth:
    """Coordinate OAuth2 credential load, refresh, and interactive login."""

    def __init__(
        self,
        client_secrets_path: Path,
        scopes: list[str] | tuple[str, ...] | None = None,
        service_name: str = "youtube_oauth",
    ) -> None:
        self._client_secrets_path = Path(client_secrets_path)
        self._scopes = tuple(
            scopes
            or (
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
            ),
        )
        self._service_name = service_name

    def authenticate(self, credential_store: CredentialStore) -> Any:
        """Load existing credentials, refresh when needed, or run the OAuth flow."""
        credentials = self._load_credentials(credential_store)
        if credentials is not None:
            try:
                credentials = self.refresh_if_needed(credentials)
            except Exception as exc:
                if self._is_refresh_token_invalid(exc):
                    credentials = None
                    credential_store.delete(self._service_name)
                else:
                    raise RuntimeError(f"Credential refresh failed: {exc}") from exc
            else:
                if getattr(credentials, "valid", False) and self._has_required_scopes(credentials):
                    self._persist_credentials(credential_store, credentials)
                    return credentials

        credentials = self._run_oauth_flow()
        credentials = self.refresh_if_needed(credentials)
        self._persist_credentials(credential_store, credentials)
        return credentials

    def refresh_if_needed(self, credentials: Any) -> Any:
        """Refresh expired credentials when a refresh token is available."""
        if (
            getattr(credentials, "expired", False)
            and getattr(credentials, "refresh_token", None)
            and callable(getattr(credentials, "refresh", None))
        ):
            if GoogleRequest is None:
                raise RuntimeError("google-auth transport is unavailable for credential refresh.")
            credentials.refresh(GoogleRequest())
        return credentials

    def _load_credentials(self, credential_store: CredentialStore) -> Any | None:
        """Reconstruct credentials from persisted credential-store payloads."""
        if GoogleCredentials is None:
            raise RuntimeError("google.oauth2.credentials is unavailable.")

        payload = credential_store.load(self._service_name)
        if not payload:
            return None

        authorized_json = payload.get("authorized_user_json")
        if isinstance(authorized_json, str) and authorized_json.strip():
            try:
                user_info = json.loads(authorized_json)
            except json.JSONDecodeError:
                user_info = None
            if isinstance(user_info, dict):
                try:
                    return GoogleCredentials.from_authorized_user_info(user_info)
                except (TypeError, ValueError):
                    return None

        try:
            return GoogleCredentials.from_authorized_user_info(payload)
        except (TypeError, ValueError):
            return None

    def _persist_credentials(self, credential_store: CredentialStore, credentials: Any) -> None:
        """Persist credentials through domain credential-store abstraction."""
        serialized = self._credentials_to_json(credentials)
        credential_store.save(
            self._service_name,
            {
                "authorized_user_json": serialized,
            },
        )

    @staticmethod
    def _credentials_to_json(credentials: Any) -> str:
        """Serialize credentials to JSON text."""
        to_json = getattr(credentials, "to_json", None)
        if callable(to_json):
            raw = to_json()
            if isinstance(raw, str):
                return raw
            if isinstance(raw, (bytes, bytearray)):
                return raw.decode("utf-8", errors="replace")
        if isinstance(credentials, dict):
            return json.dumps(credentials, ensure_ascii=False)
        return json.dumps(YouTubeAuth._credential_payload(credentials), ensure_ascii=False)

    @staticmethod
    def _credential_payload(credentials: Any) -> dict[str, Any]:
        """Build a dict payload from credential objects when to_json is unavailable."""
        payload: dict[str, Any] = {}
        for key in (
            "token",
            "refresh_token",
            "token_uri",
            "client_id",
            "client_secret",
            "scopes",
            "expiry",
        ):
            value = getattr(credentials, key, None)
            if value is None:
                continue
            payload[key] = value if isinstance(value, (str, list)) else str(value)
        return payload

    def _run_oauth_flow(self) -> Any:
        """Execute browser-based OAuth installed-app flow."""
        if InstalledAppFlow is None:
            raise RuntimeError("google-auth-oauthlib is unavailable.")
        if not self._client_secrets_path.exists():
            raise FileNotFoundError(
                f"Client secrets file not found: {self._client_secrets_path}",
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._client_secrets_path),
            list(self._scopes),
        )
        return flow.run_local_server(port=0)

    def _has_required_scopes(self, credentials: Any) -> bool:
        """Return True when credentials include all configured scopes."""
        has_scopes = getattr(credentials, "has_scopes", None)
        if callable(has_scopes):
            try:
                return bool(has_scopes(self._scopes))
            except Exception:
                return False
        return True

    @staticmethod
    def _is_refresh_token_invalid(exc: Exception) -> bool:
        """Detect revoked/invalid-grant refresh failures."""
        message = str(exc).lower()
        invalid_markers = (
            "invalid_grant",
            "expired or revoked",
            "token has been expired or revoked",
            "deleted_client",
            "unauthorized_client",
            "invalid_client",
        )
        return any(marker in message for marker in invalid_markers)

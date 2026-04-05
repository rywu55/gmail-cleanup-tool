import os
import stat
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://mail.google.com/']


class OAuthError(Exception):
    pass


def get_credentials(client_id: str, client_secret: str, token_path: str) -> Credentials:
    creds = _load_token(token_path)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
            return creds
        except Exception as e:
            raise OAuthError(f"Token refresh failed: {e}") from e

    if creds and creds.valid:
        return creds

    creds = _run_oauth_flow(client_id, client_secret)
    _save_token(creds, token_path)
    return creds


def revoke_credentials(token_path: str) -> None:
    path = Path(token_path)
    if path.exists():
        path.unlink()


def _load_token(token_path: str) -> Credentials | None:
    path = Path(token_path)
    if not path.exists():
        return None
    try:
        return Credentials.from_authorized_user_file(str(path), SCOPES)
    except Exception:
        return None


def _save_token(creds: Credentials, token_path: str) -> None:
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600


def _run_oauth_flow(client_id: str, client_secret: str) -> Credentials:
    client_config = {
        'installed': {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uris': ['http://127.0.0.1'],
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
        }
    }
    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, prompt='consent')
        return creds
    except Exception as e:
        raise OAuthError(f"OAuth flow failed: {e}") from e

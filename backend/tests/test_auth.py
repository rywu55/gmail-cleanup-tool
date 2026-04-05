import os
import stat
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from auth import OAuthError, get_credentials, revoke_credentials


def _write_token(path: Path, valid: bool = True, expired: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    token_data = {
        'token': 'access-token',
        'refresh_token': 'refresh-token',
        'client_id': 'cid',
        'client_secret': 'csecret',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'scopes': ['https://www.googleapis.com/auth/gmail.modify'],
    }
    path.write_text(json.dumps(token_data))


class TestGetCredentials:
    def test_returns_valid_credentials_from_token_file(self, tmp_path):
        token_path = tmp_path / 'token.json'
        _write_token(token_path)

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        with patch('auth.Credentials.from_authorized_user_file', return_value=mock_creds):
            result = get_credentials('cid', 'csecret', str(token_path))

        assert result is mock_creds

    def test_refreshes_expired_token_silently(self, tmp_path):
        token_path = tmp_path / 'token.json'
        _write_token(token_path)

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = 'rt'
        mock_creds.to_json.return_value = '{}'

        with patch('auth.Credentials.from_authorized_user_file', return_value=mock_creds), \
             patch('auth.Request'), \
             patch('auth.os.chmod'):
            result = get_credentials('cid', 'csecret', str(token_path))

        mock_creds.refresh.assert_called_once()
        assert result is mock_creds

    def test_raises_oauth_error_when_refresh_fails(self, tmp_path):
        token_path = tmp_path / 'token.json'
        _write_token(token_path)

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = 'rt'
        mock_creds.refresh.side_effect = Exception('refresh failed')

        with patch('auth.Credentials.from_authorized_user_file', return_value=mock_creds), \
             patch('auth.Request'):
            with pytest.raises(OAuthError, match='refresh failed'):
                get_credentials('cid', 'csecret', str(token_path))

    def test_saves_token_with_chmod_600(self, tmp_path):
        token_path = tmp_path / 'token.json'

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = False
        mock_creds.refresh_token = None
        mock_creds.to_json.return_value = '{}'

        mock_flow_creds = MagicMock()
        mock_flow_creds.to_json.return_value = '{}'

        with patch('auth.Credentials.from_authorized_user_file', side_effect=Exception), \
             patch('auth.InstalledAppFlow.from_client_config') as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow.run_local_server.return_value = mock_flow_creds
            mock_flow_cls.return_value = mock_flow

            get_credentials('cid', 'csecret', str(token_path))

        assert token_path.exists()
        file_mode = oct(stat.S_IMODE(os.stat(token_path).st_mode))
        assert file_mode == oct(0o600)

    def test_raises_oauth_error_on_denied_consent(self, tmp_path):
        token_path = tmp_path / 'token.json'

        with patch('auth.Credentials.from_authorized_user_file', side_effect=Exception), \
             patch('auth.InstalledAppFlow.from_client_config') as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow.run_local_server.side_effect = Exception('access_denied')
            mock_flow_cls.return_value = mock_flow

            with pytest.raises(OAuthError):
                get_credentials('cid', 'csecret', str(token_path))


class TestRevokeCredentials:
    def test_deletes_token_file(self, tmp_path):
        token_path = tmp_path / 'token.json'
        token_path.write_text('{}')

        revoke_credentials(str(token_path))

        assert not token_path.exists()

    def test_does_not_raise_if_token_missing(self, tmp_path):
        revoke_credentials(str(tmp_path / 'nonexistent.json'))

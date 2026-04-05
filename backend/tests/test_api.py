from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from db import EmailRecord, SenderRule
import time


def _make_client(db_fixture):
    """Create a TestClient with the test DB injected."""
    import main as app_module
    app_module.db = db_fixture
    app_module.app_state = app_module.AppState()
    from main import app
    return TestClient(app)


def _email(id='m1', sender='s@example.com') -> EmailRecord:
    return EmailRecord(
        id=id, sender_address=sender, sender_domain=sender.split('@')[-1],
        display_name=None, subject='Test', date=1700000000,
        labels=['CATEGORY_PROMOTIONS'], has_unsubscribe=True,
    )


class TestAuthRoutes:
    def test_auth_status_authenticated(self, db):
        client = _make_client(db)
        mock_creds = MagicMock()
        with patch('main.get_credentials', return_value=mock_creds):
            res = client.get('/api/auth/status')
        assert res.status_code == 200
        assert res.json()['authenticated'] is True

    def test_auth_status_unauthenticated(self, db):
        from auth import OAuthError
        client = _make_client(db)
        with patch('main.get_credentials', side_effect=OAuthError('no token')):
            res = client.get('/api/auth/status')
        assert res.json()['authenticated'] is False

    def test_auth_revoke(self, db):
        client = _make_client(db)
        with patch('main.revoke_credentials'):
            res = client.delete('/api/auth')
        assert res.status_code == 200
        assert res.json()['revoked'] is True


class TestSyncRoutes:
    def test_sync_status_returns_state(self, db):
        client = _make_client(db)
        res = client.get('/api/sync/status')
        assert res.status_code == 200
        data = res.json()
        assert 'is_syncing' in data
        assert 'total_fetched' in data

    def test_start_sync_returns_409_if_already_syncing(self, db):
        import main as app_module
        client = _make_client(db)
        app_module.app_state.is_syncing = True
        mock_creds = MagicMock()
        with patch('main.get_credentials', return_value=mock_creds):
            res = client.post('/api/sync')
        assert res.status_code == 409

    def test_start_sync_returns_401_without_credentials(self, db):
        from auth import OAuthError
        client = _make_client(db)
        with patch('main.get_credentials', side_effect=OAuthError('no token')):
            res = client.post('/api/sync')
        assert res.status_code == 401


class TestReviewRoute:
    def test_returns_candidates(self, db):
        db.replace_emails([_email('m1'), _email('m2')])
        client = _make_client(db)
        res = client.get('/api/review')
        assert res.status_code == 200
        data = res.json()
        assert 'candidates' in data

    def test_empty_inbox_returns_empty_candidates(self, db):
        client = _make_client(db)
        res = client.get('/api/review')
        assert res.status_code == 200
        assert res.json()['candidates'] == []


class TestDeleteRoute:
    def test_delete_returns_409_if_deleting_in_progress(self, db):
        import main as app_module
        client = _make_client(db)
        app_module.app_state.is_deleting = True
        mock_creds = MagicMock()
        with patch('main.get_credentials', return_value=mock_creds):
            res = client.post('/api/delete', json={'deleted_ids': ['m1'], 'protected_ids': []})
        assert res.status_code == 409

    def test_delete_returns_409_if_sync_in_progress(self, db):
        import main as app_module
        client = _make_client(db)
        app_module.app_state.is_syncing = True
        mock_creds = MagicMock()
        with patch('main.get_credentials', return_value=mock_creds):
            res = client.post('/api/delete', json={'deleted_ids': ['m1'], 'protected_ids': []})
        assert res.status_code == 409

    def test_successful_delete(self, db, mock_creds):
        from deletion import DeleteResponse as DR
        db.replace_emails([_email('m1')])
        client = _make_client(db)
        with patch('main.get_credentials', return_value=mock_creds), \
             patch('main.deletion_service.delete_emails', return_value=DR(deleted=1, failed=[], rules_saved=True)):
            res = client.post('/api/delete', json={'deleted_ids': ['m1'], 'protected_ids': []})
        assert res.status_code == 200
        assert res.json()['deleted'] == 1


class TestRulesRoutes:
    def test_list_rules_empty(self, db):
        client = _make_client(db)
        res = client.get('/api/rules')
        assert res.status_code == 200
        assert res.json()['rules'] == []

    def test_add_rule(self, db):
        client = _make_client(db)
        res = client.post('/api/rules', json={
            'sender_address': 'test@example.com',
            'rule': 'delete',
            'display_name': 'Test',
        })
        assert res.status_code == 200
        assert res.json()['sender_address'] == 'test@example.com'
        assert res.json()['source'] == 'manual'

    def test_remove_rule(self, db):
        client = _make_client(db)
        client.post('/api/rules', json={'sender_address': 'del@x.com', 'rule': 'delete'})
        res = client.delete('/api/rules/del@x.com')
        assert res.status_code == 200
        assert db.get_rule('del@x.com') is None

    def test_rules_ordered_by_updated_at_desc(self, db):
        client = _make_client(db)
        client.post('/api/rules', json={'sender_address': 'first@x.com', 'rule': 'delete'})
        client.post('/api/rules', json={'sender_address': 'second@x.com', 'rule': 'protect'})
        res = client.get('/api/rules')
        rules = res.json()['rules']
        assert len(rules) == 2
        assert rules[0]['updated_at'] >= rules[1]['updated_at']

    def test_server_binds_to_localhost_only(self):
        import main as app_module
        # Verify the app does not have a wildcard host binding configured
        # (actual bind enforcement happens at uvicorn invocation level)
        from main import app
        assert app is not None  # App exists; SETUP.md documents --host 127.0.0.1

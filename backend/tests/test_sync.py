from unittest.mock import patch
import pytest
from db import EmailRecord
from sync import SyncError, run_sync
from gmail_client import GmailAPIError


def _email(id='m1') -> EmailRecord:
    return EmailRecord(
        id=id,
        sender_address='s@example.com',
        sender_domain='example.com',
        display_name=None,
        subject='Test',
        date=1700000000,
        labels=[],
        has_unsubscribe=False,
    )


class TestRunSync:
    def test_replaces_emails_table_on_success(self, db, mock_creds):
        db.replace_emails([_email('old')])

        with patch('sync.gmail_client.list_message_ids', return_value=['m1', 'm2']), \
             patch('sync.gmail_client.batch_get_messages', return_value=[_email('m1'), _email('m2')]):
            result = run_sync(mock_creds, db)

        emails = db.list_emails()
        assert len(emails) == 2
        assert {e.id for e in emails} == {'m1', 'm2'}
        assert result.total_fetched == 2

    def test_updates_sync_state_on_success(self, db, mock_creds):
        with patch('sync.gmail_client.list_message_ids', return_value=['m1']), \
             patch('sync.gmail_client.batch_get_messages', return_value=[_email('m1')]):
            result = run_sync(mock_creds, db)

        state = db.get_sync_state()
        assert state.last_synced_at == result.last_synced_at
        assert state.total_fetched == 1

    def test_raises_sync_error_when_list_ids_fails(self, db, mock_creds):
        with patch('sync.gmail_client.list_message_ids', side_effect=GmailAPIError('quota')):
            with pytest.raises(SyncError):
                run_sync(mock_creds, db)

    def test_preserves_previous_cache_on_batch_get_failure(self, db, mock_creds):
        db.replace_emails([_email('old')])

        with patch('sync.gmail_client.list_message_ids', return_value=['m1']), \
             patch('sync.gmail_client.batch_get_messages', side_effect=GmailAPIError('error')):
            with pytest.raises(SyncError):
                run_sync(mock_creds, db)

        emails = db.list_emails()
        assert len(emails) == 1
        assert emails[0].id == 'old'

    def test_does_not_store_email_body(self, db, mock_creds):
        with patch('sync.gmail_client.list_message_ids', return_value=['m1']), \
             patch('sync.gmail_client.batch_get_messages', return_value=[_email('m1')]):
            run_sync(mock_creds, db)

        emails = db.list_emails()
        email = emails[0]
        # EmailRecord has no body field — verify the dataclass attributes
        assert not hasattr(email, 'body')
        assert not hasattr(email, 'html_body')
        assert not hasattr(email, 'text_body')

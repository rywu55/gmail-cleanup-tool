from unittest.mock import patch, MagicMock
import pytest
from db import EmailRecord, SenderRule
from deletion import delete_emails
from gmail_client import BatchDeleteResult


def _email(id='m1', sender='s@example.com') -> EmailRecord:
    return EmailRecord(
        id=id,
        sender_address=sender,
        sender_domain=sender.split('@')[-1],
        display_name=None,
        subject='Test',
        date=1700000000,
        labels=[],
        has_unsubscribe=False,
    )


class TestDeleteEmails:
    def test_successful_deletion_removes_ids_from_db(self, db, mock_creds):
        db.replace_emails([_email('m1'), _email('m2')])
        assert len(db.list_emails()) == 2

        with patch('deletion.gmail_client.batch_delete', return_value=BatchDeleteResult(deleted=2, failed=[])):
            result = delete_emails(mock_creds, db, deleted_ids=['m1', 'm2'], protected_ids=[])

        assert result.deleted == 2
        assert result.failed == []
        assert len(db.list_emails()) == 0

    def test_partial_failure_removes_only_successful_ids(self, db, mock_creds):
        db.replace_emails([_email('m1'), _email('m2')])

        with patch('deletion.gmail_client.batch_delete', return_value=BatchDeleteResult(deleted=1, failed=['m2'])):
            result = delete_emails(mock_creds, db, deleted_ids=['m1', 'm2'], protected_ids=[])

        assert result.failed == ['m2']
        remaining = [e.id for e in db.list_emails()]
        assert 'm1' not in remaining
        assert 'm2' in remaining

    def test_rules_saved_true_on_success(self, db, mock_creds):
        db.replace_emails([_email('m1', 'a@x.com')])

        with patch('deletion.gmail_client.batch_delete', return_value=BatchDeleteResult(deleted=1, failed=[])):
            result = delete_emails(mock_creds, db, deleted_ids=['m1'], protected_ids=[])

        assert result.rules_saved is True
        rule = db.get_rule('a@x.com')
        assert rule is not None
        assert rule.rule == 'delete'

    def test_rules_saved_false_on_derivation_error(self, db, mock_creds):
        db.replace_emails([_email('m1')])

        with patch('deletion.gmail_client.batch_delete', return_value=BatchDeleteResult(deleted=1, failed=[])), \
             patch('deletion.rules_engine.derive_rules_from_deletion', side_effect=Exception('db error')):
            result = delete_emails(mock_creds, db, deleted_ids=['m1'], protected_ids=[])

        assert result.deleted == 1
        assert result.rules_saved is False

    def test_empty_deleted_ids_returns_zero(self, db, mock_creds):
        result = delete_emails(mock_creds, db, deleted_ids=[], protected_ids=[])
        assert result.deleted == 0
        assert result.failed == []
        assert result.rules_saved is True

    def test_protected_ids_get_protect_rule(self, db, mock_creds):
        db.replace_emails([_email('m1', 'keep@x.com'), _email('m2', 'del@x.com')])

        with patch('deletion.gmail_client.batch_delete', return_value=BatchDeleteResult(deleted=1, failed=[])):
            delete_emails(mock_creds, db, deleted_ids=['m2'], protected_ids=['m1'])

        protect_rule = db.get_rule('keep@x.com')
        delete_rule = db.get_rule('del@x.com')
        assert protect_rule.rule == 'protect'
        assert delete_rule.rule == 'delete'

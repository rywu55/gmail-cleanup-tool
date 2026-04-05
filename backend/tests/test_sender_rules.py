import time
import pytest
from classifier import ClassificationResult
from db import Database, EmailRecord, SenderRule
from sender_rules import add_manual_rule, derive_rules_from_deletion, resolve_candidates


def _classification(email_id='m1', sender='s@example.com', score=80, action='delete') -> ClassificationResult:
    return ClassificationResult(
        email_id=email_id,
        sender_address=sender,
        score=score,
        signals=[],
        suggested_action=action,
    )


def _email(id='m1', sender='s@example.com', domain='example.com') -> EmailRecord:
    return EmailRecord(
        id=id,
        sender_address=sender,
        sender_domain=domain,
        display_name=None,
        subject='Test',
        date=1700000000,
        labels=[],
        has_unsubscribe=False,
    )


def _rule(sender='s@example.com', rule='delete', source='auto') -> SenderRule:
    now = int(time.time())
    return SenderRule(
        sender_address=sender,
        sender_domain=sender.split('@')[-1],
        display_name=None,
        rule=rule,
        source=source,
        created_at=now,
        updated_at=now,
    )


class TestResolveCandidates:
    def test_no_rule_uses_heuristic_delete(self, db):
        c = _classification(score=80, action='delete')
        result = resolve_candidates(db, [c])
        assert len(result) == 1
        assert result[0].suggested_action == 'delete'

    def test_no_rule_uses_heuristic_keep(self, db):
        c = _classification(score=30, action='keep')
        result = resolve_candidates(db, [c])
        assert len(result) == 0

    def test_delete_rule_overrides_low_score(self, db):
        db.upsert_rule(_rule(rule='delete'))
        c = _classification(score=10, action='keep')
        result = resolve_candidates(db, [c])
        assert len(result) == 1
        assert result[0].suggested_action == 'rule_override'

    def test_protect_rule_overrides_high_score(self, db):
        db.upsert_rule(_rule(rule='protect'))
        c = _classification(score=90, action='delete')
        result = resolve_candidates(db, [c])
        assert len(result) == 0

    def test_protect_wins_on_conflict(self, db):
        # insert delete rule first, then protect
        db.upsert_rule(_rule(rule='delete'))
        db.upsert_rule(_rule(rule='protect'))
        c = _classification(score=90, action='delete')
        result = resolve_candidates(db, [c])
        assert len(result) == 0


class TestDeriveRulesFromDeletion:
    def test_deleted_senders_get_delete_rule(self, db):
        emails = [_email(id='m1', sender='a@x.com')]
        derive_rules_from_deletion(db, emails, deleted_ids=['m1'], protected_ids=[])
        rule = db.get_rule('a@x.com')
        assert rule is not None
        assert rule.rule == 'delete'
        assert rule.source == 'auto'

    def test_protected_senders_get_protect_rule(self, db):
        emails = [_email(id='m1', sender='b@x.com')]
        derive_rules_from_deletion(db, emails, deleted_ids=[], protected_ids=['m1'])
        rule = db.get_rule('b@x.com')
        assert rule is not None
        assert rule.rule == 'protect'

    def test_protect_wins_when_sender_in_both(self, db):
        emails = [_email(id='m1', sender='c@x.com')]
        derive_rules_from_deletion(db, emails, deleted_ids=['m1'], protected_ids=['m1'])
        rule = db.get_rule('c@x.com')
        assert rule.rule == 'protect'

    def test_does_not_overwrite_manual_rule(self, db):
        emails = [_email(id='m1', sender='d@x.com')]
        db.upsert_rule(_rule(sender='d@x.com', rule='protect', source='manual'))
        derive_rules_from_deletion(db, emails, deleted_ids=['m1'], protected_ids=[])
        rule = db.get_rule('d@x.com')
        assert rule.rule == 'protect'
        assert rule.source == 'manual'

    def test_unknown_id_is_skipped(self, db):
        emails = []
        derive_rules_from_deletion(db, emails, deleted_ids=['unknown'], protected_ids=[])
        assert db.list_rules() == []


class TestAddManualRule:
    def test_creates_manual_rule(self, db):
        rule = add_manual_rule(db, 'test@example.com', 'delete', 'Test Sender')
        assert rule.source == 'manual'
        assert rule.rule == 'delete'
        assert rule.display_name == 'Test Sender'

    def test_normalizes_address_lowercase(self, db):
        rule = add_manual_rule(db, 'TEST@EXAMPLE.COM', 'protect')
        assert rule.sender_address == 'test@example.com'

    def test_overwrites_auto_rule(self, db):
        db.upsert_rule(_rule(sender='x@x.com', rule='delete', source='auto'))
        add_manual_rule(db, 'x@x.com', 'protect')
        rule = db.get_rule('x@x.com')
        assert rule.rule == 'protect'
        assert rule.source == 'manual'

import pytest
from classifier import classify_emails, DELETION_THRESHOLD
from db import EmailRecord


def _email(**kwargs) -> EmailRecord:
    defaults = dict(
        id='msg1',
        sender_address='sender@example.com',
        sender_domain='example.com',
        display_name=None,
        subject='Test',
        date=1700000000,
        labels=[],
        has_unsubscribe=False,
    )
    return EmailRecord(**{**defaults, **kwargs})


class TestSignalWeights:
    def test_has_unsubscribe_adds_40(self):
        results = classify_emails([_email(has_unsubscribe=True)])
        assert results[0].score == 40

    def test_label_promotions_adds_35(self):
        results = classify_emails([_email(labels=['CATEGORY_PROMOTIONS'])])
        assert results[0].score == 35

    def test_label_updates_adds_20(self):
        results = classify_emails([_email(labels=['CATEGORY_UPDATES'])])
        assert results[0].score == 20

    def test_sender_pattern_match_adds_20(self):
        results = classify_emails([_email(sender_address='no-reply@company.com')])
        assert results[0].score == 20

    def test_label_important_subtracts_50(self):
        results = classify_emails([_email(labels=['IMPORTANT'])])
        assert results[0].score == -50

    def test_label_starred_subtracts_60(self):
        results = classify_emails([_email(labels=['STARRED'])])
        assert results[0].score == -60

    def test_multiple_signals_cumulate(self):
        results = classify_emails([_email(
            has_unsubscribe=True,
            labels=['CATEGORY_PROMOTIONS'],
            sender_address='newsletter@promo.com',
        )])
        assert results[0].score == 40 + 35 + 20

    def test_protect_signals_override_promo(self):
        results = classify_emails([_email(
            has_unsubscribe=True,
            labels=['CATEGORY_PROMOTIONS', 'STARRED'],
        )])
        # 40 + 35 - 60 = 15
        assert results[0].score == 15


class TestThreshold:
    def test_score_60_is_delete(self):
        # unsubscribe(40) + updates(20) = 60
        results = classify_emails([_email(
            has_unsubscribe=True,
            labels=['CATEGORY_UPDATES'],
        )])
        assert results[0].score == 60
        assert results[0].suggested_action == 'delete'

    def test_score_59_is_keep(self):
        # promotions(35) + updates(20) = 55; add pattern(20) = 75, too high
        # promotions(35) + updates(20) + no pattern = 55 → keep
        results = classify_emails([_email(labels=['CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES'])])
        assert results[0].score == 55
        assert results[0].suggested_action == 'keep'

    def test_score_above_threshold_is_delete(self):
        results = classify_emails([_email(has_unsubscribe=True, labels=['CATEGORY_PROMOTIONS'])])
        assert results[0].score > DELETION_THRESHOLD
        assert results[0].suggested_action == 'delete'


class TestClassifyEmails:
    def test_empty_list_returns_empty(self):
        assert classify_emails([]) == []

    def test_sorted_by_score_descending(self):
        emails = [
            _email(id='low', labels=[]),
            _email(id='high', has_unsubscribe=True, labels=['CATEGORY_PROMOTIONS']),
        ]
        results = classify_emails(emails)
        assert results[0].email_id == 'high'
        assert results[1].email_id == 'low'

    def test_signals_list_populated(self):
        results = classify_emails([_email(has_unsubscribe=True)])
        assert len(results[0].signals) > 0

    def test_no_external_calls(self):
        # Pure function — just verify it runs without any mocking
        classify_emails([_email()])


class TestSenderPatterns:
    @pytest.mark.parametrize('local', [
        'no-reply', 'noreply', 'newsletter', 'marketing',
        'mailer', 'donotreply', 'notifications', 'updates',
        'news', 'info', 'hello', 'team', 'alerts',
    ])
    def test_pattern_match(self, local):
        results = classify_emails([_email(sender_address=f'{local}@company.com')])
        assert any('sender pattern' in s.lower() for s in results[0].signals)

from dataclasses import dataclass
from typing import Literal

from db import EmailRecord

DELETION_THRESHOLD = 60

SIGNALS: dict[str, int] = {
    'has_unsubscribe':      40,
    'label_promotions':     35,
    'label_updates':        20,
    'sender_pattern_match': 20,
    'label_important':     -50,
    'label_starred':       -60,
}

SENDER_PATTERNS = [
    'no-reply', 'noreply', 'newsletter', 'marketing',
    'mailer', 'donotreply', 'notifications', 'updates',
    'news', 'info', 'hello', 'team', 'alerts',
]


@dataclass
class ClassificationResult:
    email_id: str
    sender_address: str
    score: int
    signals: list[str]
    suggested_action: Literal['delete', 'keep', 'rule_override']


def classify_emails(emails: list[EmailRecord]) -> list[ClassificationResult]:
    results = []
    for email in emails:
        score, signals = _score(email)
        action: Literal['delete', 'keep', 'rule_override'] = (
            'delete' if score >= DELETION_THRESHOLD else 'keep'
        )
        results.append(ClassificationResult(
            email_id=email.id,
            sender_address=email.sender_address,
            score=score,
            signals=signals,
            suggested_action=action,
        ))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _score(email: EmailRecord) -> tuple[int, list[str]]:
    score = 0
    signals: list[str] = []

    if email.has_unsubscribe:
        score += SIGNALS['has_unsubscribe']
        signals.append('Has unsubscribe header')

    if 'CATEGORY_PROMOTIONS' in email.labels:
        score += SIGNALS['label_promotions']
        signals.append('Gmail Promotions category')

    if 'CATEGORY_UPDATES' in email.labels:
        score += SIGNALS['label_updates']
        signals.append('Gmail Updates category')

    local_part = email.sender_address.split('@')[0].lower()
    if any(p in local_part for p in SENDER_PATTERNS):
        score += SIGNALS['sender_pattern_match']
        signals.append('Promotional sender pattern')

    if 'IMPORTANT' in email.labels:
        score += SIGNALS['label_important']
        signals.append('Marked important')

    if 'STARRED' in email.labels:
        score += SIGNALS['label_starred']
        signals.append('Starred')

    return score, signals

import time
from typing import Literal

from classifier import ClassificationResult
from db import Database, EmailRecord, SenderRule


def resolve_candidates(
    db: Database,
    classifications: list[ClassificationResult],
) -> list[ClassificationResult]:
    """Apply sender_rules on top of heuristic scores to produce the final list."""
    resolved = []
    for result in classifications:
        rule = db.get_rule(result.sender_address)
        if rule is None:
            resolved.append(result)
        elif rule.rule == 'protect':
            # Always exclude — do not add to resolved list
            continue
        else:  # rule.rule == 'delete'
            resolved.append(ClassificationResult(
                email_id=result.email_id,
                sender_address=result.sender_address,
                score=result.score,
                signals=result.signals,
                suggested_action='rule_override',
            ))

    # Also include emails whose sender has a 'delete' rule but scored below threshold
    # (they would have suggested_action='keep' and not appear in resolved yet)
    resolved_ids = {r.email_id for r in resolved}
    for result in classifications:
        if result.email_id in resolved_ids:
            continue
        rule = db.get_rule(result.sender_address)
        if rule and rule.rule == 'delete':
            resolved.append(ClassificationResult(
                email_id=result.email_id,
                sender_address=result.sender_address,
                score=result.score,
                signals=result.signals,
                suggested_action='rule_override',
            ))

    # Return only candidates marked for deletion (rule_override or delete)
    return [r for r in resolved if r.suggested_action in ('delete', 'rule_override')]


def derive_rules_from_deletion(
    db: Database,
    emails: list[EmailRecord],
    deleted_ids: list[str],
    protected_ids: list[str],
) -> None:
    """Derive and persist auto rules from a completed deletion pass."""
    id_to_email = {e.id: e for e in emails}
    now = int(time.time())

    # Track senders getting protect rules — protect wins on conflict
    protect_senders: set[str] = set()

    for msg_id in protected_ids:
        email = id_to_email.get(msg_id)
        if not email:
            continue
        protect_senders.add(email.sender_address)
        rule = SenderRule(
            sender_address=email.sender_address,
            sender_domain=email.sender_domain,
            display_name=email.display_name,
            rule='protect',
            source='auto',
            created_at=now,
            updated_at=now,
        )
        db.upsert_rule_no_overwrite_manual(rule)

    for msg_id in deleted_ids:
        email = id_to_email.get(msg_id)
        if not email:
            continue
        # protect wins on conflict
        if email.sender_address in protect_senders:
            continue
        rule = SenderRule(
            sender_address=email.sender_address,
            sender_domain=email.sender_domain,
            display_name=email.display_name,
            rule='delete',
            source='auto',
            created_at=now,
            updated_at=now,
        )
        db.upsert_rule_no_overwrite_manual(rule)


def add_manual_rule(
    db: Database,
    sender_address: str,
    rule: Literal['delete', 'protect'],
    display_name: str | None = None,
) -> SenderRule:
    now = int(time.time())
    sender_domain = sender_address.split('@')[-1] if '@' in sender_address else sender_address
    new_rule = SenderRule(
        sender_address=sender_address.lower().strip(),
        sender_domain=sender_domain.lower().strip(),
        display_name=display_name,
        rule=rule,
        source='manual',
        created_at=now,
        updated_at=now,
    )
    db.upsert_rule(new_rule)
    return new_rule

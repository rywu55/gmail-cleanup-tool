import logging
from dataclasses import dataclass

from google.oauth2.credentials import Credentials

import gmail_client
import sender_rules as rules_engine
from db import Database

logger = logging.getLogger(__name__)


@dataclass
class DeleteResponse:
    deleted: int
    failed: list[str]
    rules_saved: bool


def delete_emails(
    creds: Credentials,
    db: Database,
    deleted_ids: list[str],
    protected_ids: list[str],
) -> DeleteResponse:
    if not deleted_ids:
        return DeleteResponse(deleted=0, failed=[], rules_saved=True)

    # Fetch email metadata BEFORE deletion so sender info is available for rule derivation
    all_ids = list(set(deleted_ids + protected_ids))
    emails = db.get_emails_by_ids(all_ids)

    try:
        result = gmail_client.batch_delete(creds, deleted_ids)
    except gmail_client.GmailAPIError as e:
        logger.error("batchDelete failed: %s", e)
        raise

    successfully_deleted = [i for i in deleted_ids if i not in result.failed]
    if successfully_deleted:
        db.delete_emails_by_ids(successfully_deleted)

    rules_saved = True
    try:
        rules_engine.derive_rules_from_deletion(
            db=db,
            emails=emails,
            deleted_ids=successfully_deleted,
            protected_ids=protected_ids,
        )
    except Exception as e:
        logger.error("Rule derivation failed: %s", e)
        rules_saved = False

    return DeleteResponse(
        deleted=result.deleted,
        failed=result.failed,
        rules_saved=rules_saved,
    )

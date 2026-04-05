import time
from dataclasses import dataclass

from google.oauth2.credentials import Credentials

import gmail_client
from db import Database
from gmail_client import GmailAPIError


@dataclass
class SyncResult:
    total_fetched: int
    last_synced_at: int


class SyncError(Exception):
    pass


def run_sync(creds: Credentials, db: Database) -> SyncResult:
    try:
        ids = gmail_client.list_message_ids(creds, max_results=200)
    except GmailAPIError as e:
        raise SyncError(f"Failed to list message IDs: {e}") from e

    try:
        records = gmail_client.batch_get_messages(creds, ids)
    except GmailAPIError as e:
        raise SyncError(f"Failed to fetch message metadata: {e}") from e

    db.replace_emails(records)

    now = int(time.time())
    db.set_sync_state(last_synced_at=now, total_fetched=len(records))

    return SyncResult(total_fetched=len(records), last_synced_at=now)

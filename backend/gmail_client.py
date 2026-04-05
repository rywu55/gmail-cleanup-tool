import base64
import email as email_lib
import time
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from db import EmailRecord

BATCH_GET_SIZE = 100
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class GmailAPIError(Exception):
    pass


@dataclass
class BatchDeleteResult:
    deleted: int
    failed: list[str]


def _build_service(creds: Credentials):
    return build('gmail', 'v1', credentials=creds)


def _with_retry(fn):
    """Retry fn up to MAX_RETRIES times on 429/5xx with exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503, 504):
                if attempt == MAX_RETRIES - 1:
                    raise GmailAPIError(f"Gmail API failed after {MAX_RETRIES} retries: {e}") from e
                time.sleep(BACKOFF_BASE ** attempt)
            else:
                raise GmailAPIError(f"Gmail API error: {e}") from e


def list_message_ids(creds: Credentials, max_results: int = 200) -> list[str]:
    service = _build_service(creds)
    ids = []
    page_token = None

    while len(ids) < max_results:
        batch_size = min(500, max_results - len(ids))

        def _list(pt=page_token, bs=batch_size):
            params = {'userId': 'me', 'maxResults': bs}
            if pt:
                params['pageToken'] = pt
            return service.users().messages().list(**params).execute()

        result = _with_retry(_list)
        messages = result.get('messages', [])
        ids.extend(m['id'] for m in messages)
        page_token = result.get('nextPageToken')
        if not page_token:
            break

    return ids[:max_results]


def batch_get_messages(creds: Credentials, ids: list[str]) -> list[EmailRecord]:
    service = _build_service(creds)
    records = []

    for chunk_start in range(0, len(ids), BATCH_GET_SIZE):
        chunk = ids[chunk_start: chunk_start + BATCH_GET_SIZE]
        chunk_records = []

        def _batch_get(c=chunk):
            results = []
            batch = service.new_batch_http_request()

            def _callback(request_id, response, exception):
                if exception:
                    return  # skip failed individual messages
                results.append(response)

            for msg_id in c:
                batch.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date', 'List-Unsubscribe'],
                    ),
                    callback=_callback,
                )
            batch.execute()
            return results

        raw_messages = _with_retry(_batch_get)
        for msg in raw_messages:
            record = _parse_message(msg)
            if record:
                chunk_records.append(record)

        records.extend(chunk_records)

    return records


def batch_delete(creds: Credentials, ids: list[str]) -> BatchDeleteResult:
    if not ids:
        return BatchDeleteResult(deleted=0, failed=[])

    service = _build_service(creds)

    try:
        def _delete():
            service.users().messages().batchDelete(
                userId='me',
                body={'ids': ids},
            ).execute()

        _with_retry(_delete)
        return BatchDeleteResult(deleted=len(ids), failed=[])
    except GmailAPIError as e:
        # batchDelete doesn't report per-ID failures — if it fails, all IDs failed
        raise e


def _parse_message(msg: dict) -> EmailRecord | None:
    try:
        msg_id = msg['id']
        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        labels = msg.get('labelIds', [])

        from_raw = headers.get('From', '')
        sender_address, display_name = _parse_from(from_raw)
        sender_domain = sender_address.split('@')[-1] if '@' in sender_address else ''

        subject = headers.get('Subject', '(no subject)')

        date_str = headers.get('Date', '')
        date_ts = _parse_date(date_str, msg.get('internalDate'))

        has_unsubscribe = 'List-Unsubscribe' in headers

        return EmailRecord(
            id=msg_id,
            sender_address=sender_address.lower().strip(),
            sender_domain=sender_domain.lower().strip(),
            display_name=display_name or None,
            subject=subject,
            date=date_ts,
            labels=labels,
            has_unsubscribe=has_unsubscribe,
        )
    except Exception:
        return None


def _parse_from(from_header: str) -> tuple[str, str]:
    """Return (email_address, display_name) from a From header value."""
    try:
        parsed = email_lib.headerregistry.Address(addr_spec=from_header)
        return parsed.addr_spec, parsed.display_name
    except Exception:
        pass
    # fallback: extract <email> pattern
    if '<' in from_header and '>' in from_header:
        display = from_header[:from_header.index('<')].strip().strip('"')
        addr = from_header[from_header.index('<') + 1: from_header.index('>')].strip()
        return addr, display
    return from_header.strip(), ''


def _parse_date(date_str: str, internal_date: str | None) -> int:
    """Return Unix timestamp. Fall back to internalDate (ms) if header parse fails."""
    if internal_date:
        return int(internal_date) // 1000
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(date_str).timestamp())
    except Exception:
        return 0

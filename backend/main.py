import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import classifier
import deletion as deletion_service
import sender_rules as rules_engine
import sync as sync_service
from auth import OAuthError, get_credentials, revoke_credentials
from config import settings
from db import Database


# --- App state ---

class AppState:
    def __init__(self):
        self.is_syncing = False
        self.is_deleting = False
        self._lock = threading.Lock()

    def start_sync(self) -> bool:
        with self._lock:
            if self.is_syncing or self.is_deleting:
                return False
            self.is_syncing = True
            return True

    def stop_sync(self):
        with self._lock:
            self.is_syncing = False

    def start_delete(self) -> bool:
        with self._lock:
            if self.is_deleting or self.is_syncing:
                return False
            self.is_deleting = True
            return True

    def stop_delete(self):
        with self._lock:
            self.is_deleting = False


app_state = AppState()
db: Database | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = Database(settings.db_path)
    yield
    if db:
        db.close()


# --- App ---

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_methods=['*'],
    allow_headers=['*'],
)


# --- Pydantic models ---

class SyncStatusResponse(BaseModel):
    last_synced_at: int | None
    total_fetched: int
    is_syncing: bool


class ReviewRow(BaseModel):
    email_id: str
    sender_address: str
    display_name: str | None
    subject: str
    date: int
    pre_selected: bool
    reason: str | None


class ReviewResponse(BaseModel):
    emails: list[ReviewRow]


class DeleteRequest(BaseModel):
    deleted_ids: list[str]
    protected_ids: list[str]


class DeleteResponse(BaseModel):
    deleted: int
    failed: list[str]
    rules_saved: bool


class SenderRuleResponse(BaseModel):
    sender_address: str
    sender_domain: str
    display_name: str | None
    rule: Literal['delete', 'protect']
    source: Literal['auto', 'manual']
    created_at: int
    updated_at: int


class SenderRulesListResponse(BaseModel):
    rules: list[SenderRuleResponse]


class SenderRuleRequest(BaseModel):
    sender_address: str
    rule: Literal['delete', 'protect']
    display_name: str | None = None


# --- Auth routes ---

@app.get('/api/auth/status')
def auth_status():
    try:
        get_credentials(settings.client_id, settings.client_secret, settings.token_path)
        return {'authenticated': True}
    except OAuthError:
        return {'authenticated': False}


@app.get('/api/auth/start')
def auth_start():
    try:
        get_credentials(settings.client_id, settings.client_secret, settings.token_path)
        return {'authenticated': True}
    except OAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.delete('/api/auth')
def auth_revoke():
    revoke_credentials(settings.token_path)
    return {'revoked': True}


# --- Sync routes ---

@app.post('/api/sync')
def start_sync():
    if not app_state.start_sync():
        raise HTTPException(status_code=409, detail='Sync or deletion already in progress')

    try:
        creds = get_credentials(settings.client_id, settings.client_secret, settings.token_path)
    except OAuthError as e:
        app_state.stop_sync()
        raise HTTPException(status_code=401, detail=str(e))

    def _run():
        try:
            sync_service.run_sync(creds, db)
        except sync_service.SyncError:
            pass  # sync state preserved by run_sync on failure
        finally:
            app_state.stop_sync()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    state = db.get_sync_state()
    return SyncStatusResponse(
        last_synced_at=state.last_synced_at,
        total_fetched=state.total_fetched,
        is_syncing=True,
    )


@app.get('/api/sync/status')
def sync_status() -> SyncStatusResponse:
    state = db.get_sync_state()
    return SyncStatusResponse(
        last_synced_at=state.last_synced_at,
        total_fetched=state.total_fetched,
        is_syncing=app_state.is_syncing,
    )


# --- Review route ---

@app.get('/api/review')
def get_review() -> ReviewResponse:
    emails = db.list_emails()  # already ordered date DESC
    classifications = classifier.classify_emails(emails)
    candidates = rules_engine.resolve_candidates(db, classifications)

    candidate_ids = {c.email_id: c for c in candidates}

    rows = []
    for email in emails:
        c = candidate_ids.get(email.id)
        pre_selected = c is not None
        reason = None
        if c:
            reason = 'Learned rule' if c.suggested_action == 'rule_override' else 'Promotional signals'
        rows.append(ReviewRow(
            email_id=email.id,
            sender_address=email.sender_address,
            display_name=email.display_name,
            subject=email.subject,
            date=email.date,
            pre_selected=pre_selected,
            reason=reason,
        ))

    return ReviewResponse(emails=rows)


# --- Delete route ---

@app.post('/api/delete')
def delete(body: DeleteRequest) -> DeleteResponse:
    if not app_state.start_delete():
        raise HTTPException(status_code=409, detail='Deletion or sync already in progress')

    try:
        creds = get_credentials(settings.client_id, settings.client_secret, settings.token_path)
    except OAuthError as e:
        app_state.stop_delete()
        raise HTTPException(status_code=401, detail=str(e))

    try:
        result = deletion_service.delete_emails(
            creds=creds,
            db=db,
            deleted_ids=body.deleted_ids,
            protected_ids=body.protected_ids,
        )
        return DeleteResponse(
            deleted=result.deleted,
            failed=result.failed,
            rules_saved=result.rules_saved,
        )
    except deletion_service.gmail_client.GmailAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        app_state.stop_delete()


# --- Sender rules routes ---

@app.get('/api/rules')
def list_rules() -> SenderRulesListResponse:
    rules = db.list_rules()
    return SenderRulesListResponse(rules=[
        SenderRuleResponse(
            sender_address=r.sender_address,
            sender_domain=r.sender_domain,
            display_name=r.display_name,
            rule=r.rule,
            source=r.source,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rules
    ])


@app.post('/api/rules')
def add_rule(body: SenderRuleRequest) -> SenderRuleResponse:
    rule = rules_engine.add_manual_rule(
        db=db,
        sender_address=body.sender_address,
        rule=body.rule,
        display_name=body.display_name,
    )
    return SenderRuleResponse(
        sender_address=rule.sender_address,
        sender_domain=rule.sender_domain,
        display_name=rule.display_name,
        rule=rule.rule,
        source=rule.source,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@app.delete('/api/rules/{sender_address}')
def remove_rule(sender_address: str):
    db.delete_rule(sender_address)
    return {'deleted': True}

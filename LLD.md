# Gmail Cleanup Tool — Low Level Design

## 1. Overview

The Gmail Cleanup Tool is a locally-hosted SPA backed by a Python FastAPI server. The backend authenticates with Gmail via OAuth 2.0, fetches up to 1,000 email metadata records per session, and caches the minimum fields needed for classification and display. The core loop is: sync → classify → review → delete → learn. The frontend provides three views: Inbox Overview, Deletion Review, and Sender Rules. All filtering is sender-based; no complex query filtering is needed.

---

## 2. Data Structures

### SQLite — `emails` table

```sql
CREATE TABLE emails (
    id              TEXT PRIMARY KEY,   -- Gmail message ID
    sender_address  TEXT NOT NULL,      -- parsed email address
    sender_domain   TEXT NOT NULL,      -- domain portion of sender_address
    display_name    TEXT,               -- "Name" portion of From header, if present
    subject         TEXT NOT NULL,
    date            INTEGER NOT NULL,   -- Unix timestamp (UTC)
    labels          TEXT NOT NULL,      -- JSON array e.g. ["CATEGORY_PROMOTIONS", "UNREAD"]
    has_unsubscribe INTEGER NOT NULL    -- 1 if List-Unsubscribe header present, else 0
);
```

### SQLite — `sender_rules` table

```sql
CREATE TABLE sender_rules (
    sender_address  TEXT PRIMARY KEY,
    sender_domain   TEXT NOT NULL,
    display_name    TEXT,
    rule            TEXT NOT NULL CHECK (rule IN ('delete', 'protect')),
    source          TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
    -- 'auto'   = derived from user confirming or deselecting during deletion
    -- 'manual' = explicitly added by user via Sender Rules UI
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
```

### SQLite — `sync_state` table

```sql
CREATE TABLE sync_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- single-row table
    last_synced_at  INTEGER,            -- Unix timestamp, NULL if never synced
    total_fetched   INTEGER DEFAULT 0
);
```

### Python — Core types

```python
@dataclass
class EmailRecord:
    id: str
    sender_address: str
    sender_domain: str
    display_name: str | None
    subject: str
    date: int                 # Unix timestamp
    labels: list[str]
    has_unsubscribe: bool

@dataclass
class SenderRule:
    sender_address: str
    sender_domain: str
    display_name: str | None
    rule: Literal['delete', 'protect']
    source: Literal['auto', 'manual']
    created_at: int
    updated_at: int

@dataclass
class ClassificationResult:
    email_id: str
    sender_address: str
    score: int                          # 0–100 promotional likelihood
    signals: list[str]                  # human-readable reasons shown in UI
    suggested_action: Literal['delete', 'keep', 'rule_override']
```

### REST API shapes

```python
# POST /api/sync
class SyncStatusResponse(BaseModel):
    last_synced_at: int | None
    total_fetched: int
    is_syncing: bool

# GET /api/review
class ReviewResponse(BaseModel):
    candidates: list[ReviewRow]   # pre-selected for deletion, ordered by sender

class ReviewRow(BaseModel):
    email_id: str
    sender_address: str
    display_name: str | None
    subject: str
    date: int
    reason: str                   # e.g. "Learned rule" or "Promotional signals"

# POST /api/delete
class DeleteRequest(BaseModel):
    deleted_ids: list[str]        # confirmed for deletion
    protected_ids: list[str]      # deselected by user

class DeleteResponse(BaseModel):
    deleted: int
    failed: list[str]

# GET /api/rules
# POST /api/rules
# DELETE /api/rules/{sender_address}
class SenderRuleRequest(BaseModel):
    sender_address: str
    rule: Literal['delete', 'protect']
    display_name: str | None = None
```

---

## 3. Module / Component Breakdown

| Module | File path | Responsibility | Does NOT own |
|---|---|---|---|
| **Auth** | `backend/auth.py` | OAuth flow, token load/save/refresh | Gmail data fetching |
| **Gmail Client** | `backend/gmail_client.py` | `messages.list`, `batchGet` (metadata only), `batchDelete` | Business logic |
| **Sync Service** | `backend/sync.py` | Fetches 1,000 IDs, batch-gets metadata, writes to `emails` table | Classification |
| **DB** | `backend/db.py` | SQLite connection, schema init, CRUD for all three tables | API logic |
| **Classifier** | `backend/classifier.py` | Scores each email 0–100 using local signals; no external calls | Rule persistence |
| **Sender Rules Engine** | `backend/sender_rules.py` | Resolves final deletion candidates; derives and persists rules post-delete | Heuristic scoring |
| **Deletion Service** | `backend/deletion.py` | Calls `batchDelete`, removes deleted IDs from cache, triggers rule derivation | Classification |
| **API Router** | `backend/main.py` | FastAPI routes, Pydantic validation, CORS localhost-only | Business logic |
| **Config** | `backend/config.py` | Loads `.env`, exposes typed settings | Validation |
| **Frontend App** | `frontend/src/App.tsx` | SPA shell, sidebar nav | Data fetching |
| **Review View** | `frontend/src/views/Review.tsx` | Pre-selected deletion list; deselect rows; confirm action | Classification logic |
| **Sender Rules View** | `frontend/src/views/SenderRules.tsx` | Display, add, remove sender rules | Deletion |
| **API Client** | `frontend/src/api.ts` | Typed fetch wrappers for all backend endpoints | State management |

---

## 4. Key Interfaces and Contracts

### Auth

```python
def get_credentials() -> Credentials
# Loads token.json if present and valid; refreshes if expired.
# Triggers browser OAuth flow if no valid token exists.
# Raises: OAuthError if user denies or flow fails.

def revoke_credentials() -> None
# Revokes token with Google and deletes token.json.
```

### Gmail Client

```python
def list_message_ids(creds: Credentials, max_results: int = 1000) -> list[str]
# Returns up to max_results IDs, newest-first, paginating via nextPageToken.

def batch_get_messages(creds: Credentials, ids: list[str]) -> list[EmailRecord]
# Fetches metadata in chunks of 100 (Gmail batch limit).
# Parses only: sender, subject, date, labels, List-Unsubscribe header presence.

def batch_delete(creds: Credentials, ids: list[str]) -> BatchDeleteResult
# Precondition: len(ids) <= 1000
# Returns: BatchDeleteResult(deleted=int, failed=list[str])
```

### Classifier

```python
SIGNALS = {
    'has_unsubscribe':          40,
    'label_promotions':         35,
    'label_updates':            20,
    'sender_pattern_match':     20,   # no-reply, newsletter, mailer, etc.
    'label_important':         -50,
    'label_starred':           -60,
}
DELETION_THRESHOLD = 60

def classify_emails(emails: list[EmailRecord]) -> list[ClassificationResult]
# Scores each email; does not consult sender_rules.
```

### Sender Rules Engine

```python
def resolve_candidates(
    db: Database,
    classifications: list[ClassificationResult]
) -> list[ClassificationResult]
# Applies sender_rules on top of heuristic scores:
#   rule='delete' → suggested_action='rule_override' (always pre-select)
#   rule='protect' → suggested_action='keep' (always exclude)
#   no rule → use score vs. DELETION_THRESHOLD

def derive_rules_from_deletion(
    db: Database,
    deleted_ids: list[str],
    protected_ids: list[str]
) -> None
# Upserts 'delete' rules for senders of deleted_ids (source='auto').
# Upserts 'protect' rules for senders of protected_ids (source='auto').
# 'protect' wins if a sender appears in both lists.
# Manual rules are never overwritten by auto-derivation.
```

---

## 5. Control Flow

### Auth Flow

```
App starts → backend checks for token.json
    → missing/invalid: return auth_required=true
    → frontend shows Connect Gmail screen
    → user clicks Connect → GET /api/auth/start
    → browser opens Google consent screen
    → callback to localhost → tokens saved (chmod 600)
    → frontend redirects to Review
```

### Sync + Classify Flow

```
User clicks Sync (or first load post-auth)
    → POST /api/sync
    → list_message_ids() → up to 1,000 IDs
    → batch_get_messages() in chunks of 100 → EmailRecords written to SQLite
    → classify_emails() scores all records
    → resolve_candidates() applies sender rules
    → GET /api/review → pre-selected list returned to frontend
```

### Deletion Flow

```
User reviews pre-selected list
    → deselects any emails to keep
    → clicks "Delete X emails"
    → confirmation dialog
    → POST /api/delete { deleted_ids, protected_ids }
    → batch_delete() called for deleted_ids
    → deleted IDs removed from emails table
    → derive_rules_from_deletion() persists sender rules
    → frontend shows result count
    → user clicks Re-sync for next batch
```

---

## 6. Trade-offs and Decisions

### DR-001: Minimal metadata cache

**Decision:** Cache only the fields needed for classification and display: sender, subject, date, labels, unsubscribe flag.

**Criteria:** Privacy, simplicity, focus on deletion.

**Rationale:** The app's goal is deletion, not email search or archival. Storing body content or extended metadata adds disk footprint and privacy risk with no benefit to the core workflow.

**Consequences:** Features requiring body content (e.g., body keyword search) are not possible without live API calls.

---

### DR-002: SQLite over in-memory store

**Decision:** SQLite for both `emails` and `sender_rules`.

**Criteria:** Persistence of learned rules across sessions, zero operational overhead.

**Rationale:** `sender_rules` must survive restarts — that's the core value of the learning loop. SQLite is the simplest persistent store with no server dependency. The `emails` cache is a bonus that avoids re-syncing on every page load.

**Consequences:** Cache schema changes require a wipe-and-resync (acceptable — cache is disposable; rules are not).

---

### DR-003: Implicit rule learning from deletion outcome

**Decision:** Deletion action → `delete` rule; deselection → `protect` rule. No explicit flagging step.

**Criteria:** Minimal user friction, correct intent capture.

**Rationale:** The deletion action is the signal. Requiring a separate "flag this sender" step duplicates effort. Deselection is an equally clear signal in the opposite direction.

**Consequences:** An accidental deletion creates an auto `delete` rule. Mitigation: Sender Rules UI lets users review and remove any rule at any time. Manual rules are never overwritten by auto-derivation.

---

### DR-004: `protect` wins over `delete` on conflict

**Decision:** If a sender has both rule types (edge case), `protect` wins.

**Criteria:** Risk of unwanted data loss vs. minor inconvenience.

**Rationale:** Accidental deletion is harder to recover from than a missed cleanup pass. Conservative default is correct here.

**Consequences:** To flip a protected sender to `delete`, the user must first remove the `protect` rule via the Sender Rules UI.

---

### DR-005: Full cache replace on re-sync

**Decision:** Each sync wipes the `emails` table and fetches a fresh 1,000.

**Criteria:** Simplicity, correctness for the session-based cleanup model.

**Rationale:** The user always wants the most recent 1,000 after a deletion pass. Incremental sync adds complexity (handling deletions, ordering, label changes) with no benefit given the session model. `sender_rules` is never wiped on sync.

**Consequences:** Re-sync always costs ~10 batch API requests. Acceptable given the 1,000-email cap.

---

## 7. Error Handling Strategy

| Failure | Propagation | Caller sees | Recovery |
|---|---|---|---|
| OAuth token expired | `auth.py` auto-refreshes | Transparent | If refresh fails → `401`, frontend shows Reconnect prompt |
| Gmail API 429 / 5xx | Exponential backoff, 3 retries in `gmail_client.py` | `503` with retry hint | User retries sync |
| `batchDelete` partial failure | Per-ID failure list returned | Failed IDs shown in UI | User can re-sync and retry |
| Rule derivation DB failure | Logged; deletion result still returned | UI warning: "Rules not saved — review manually" | User re-adds rules via Sender Rules UI |

---

## 8. State and Lifecycle

### Sync State

```
never_synced → syncing       (POST /api/sync)
syncing      → synced        (all records written)
syncing      → sync_failed   (API or DB error)
synced       → syncing       (user re-syncs)
```

`is_syncing` is held in FastAPI app state (in-memory). A process restart resets it to `false`.

### Sender Rule Lifecycle

```
(no rule)  →  delete / protect    (auto: from deletion pass)
(no rule)  →  delete / protect    (manual: via Sender Rules UI)
delete     →  protect             (user edits in Sender Rules UI)
protect    →  delete              (user edits in Sender Rules UI)
any rule   →  (no rule)           (user removes rule; falls back to heuristic)
```

Manual rules are never overwritten by auto-derivation.

---

## 9. Dependencies

| Dependency | Why chosen | Removal cost |
|---|---|---|
| `google-auth-oauthlib` | Official OAuth 2.0 library for token flow and refresh | High |
| `google-api-python-client` | Official Gmail API client; handles batch HTTP parsing | High |
| `fastapi` + `uvicorn` | Minimal async Python web framework with Pydantic validation built in | Medium |
| `python-dotenv` | `.env` config loading | Very low |
| `react` + `vite` | SPA framework | High |
| `tailwindcss` | Utility CSS; purely presentational | Low |

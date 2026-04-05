# Plan: Gmail Cleanup Tool

**EARS spec:** `EARS.md`
**LLD:** `LLD.md`
**HLD:** `HLD.md`
**Date:** 2026-04-02

---

## Pre-conditions

Before work begins, confirm:

- [ ] HLD approved
- [ ] LLD approved
- [ ] EARS requirements approved
- [ ] Google Cloud project created with Gmail API enabled (see `SETUP.md`)
- [ ] OAuth 2.0 Desktop app credentials created and `.env` populated
- [ ] Python 3.11+ and Node 18+ installed on development machine

---

## Implementation Tasks

### 1. Project Scaffold

- [ ] Create `backend/` directory with `requirements.txt` — `fastapi`, `uvicorn`, `google-auth-oauthlib`, `google-api-python-client`, `python-dotenv`
- [ ] Create `frontend/` using `npm create vite@latest` with React + TypeScript template
- [ ] Install Tailwind CSS in `frontend/` per Vite integration guide
- [ ] Create `.env.example` with `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PORT=8080`
- [ ] Create `.gitignore` — exclude `.env`, `venv/`, `~/.gmail-cleanup/`, `*.db`
- [ ] Add `msw` and `@testing-library/react` to `frontend/` dev dependencies for component + API mocking

**Covers:** Pre-conditions

---

### 2. Database Layer

- [ ] Create `backend/db.py` — SQLite connection, `init_db()` that creates all three tables on first run
- [ ] Add `emails` table schema: `id`, `sender_address`, `sender_domain`, `display_name`, `subject`, `date`, `labels`, `has_unsubscribe`
- [ ] Add `sender_rules` table schema: `sender_address`, `sender_domain`, `display_name`, `rule`, `source`, `created_at`, `updated_at`
- [ ] Add `sync_state` table schema: single-row with `last_synced_at`, `total_fetched`
- [ ] Add CRUD functions: `upsert_emails()`, `delete_emails_by_ids()`, `get_sync_state()`, `set_sync_state()`
- [ ] Add CRUD functions: `upsert_rule()`, `delete_rule()`, `list_rules()`, `get_rule_by_address()`

**Covers:** REQ-009, REQ-023, REQ-026, REQ-027, REQ-028, REQ-031, REQ-032, REQ-033

---

### 3. Configuration

- [ ] Create `backend/config.py` — load `.env`, expose typed `Settings` object (`client_id`, `client_secret`, `port`, `db_path`)
- [ ] Set `db_path` default to `~/.gmail-cleanup/gmail_cleanup.db`
- [ ] Set token path default to `~/.gmail-cleanup/token.json`

**Covers:** REQ-037, REQ-038

---

### 4. Authentication

- [ ] Create `backend/auth.py` — `get_credentials()`: load token.json, refresh if expired, trigger browser OAuth flow if missing
- [ ] Implement OAuth callback server on `127.0.0.1` to receive authorization code
- [ ] Save token to `~/.gmail-cleanup/token.json` with `os.chmod(path, 0o600)` immediately after write
- [ ] Implement `revoke_credentials()`: revoke with Google, delete token.json
- [ ] Raise `OAuthError` on denied consent or failed flow

**Covers:** REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-037

---

### 5. Gmail Client

- [ ] Create `backend/gmail_client.py` — `list_message_ids(creds, max_results=1000)`: paginate `messages.list` newest-first
- [ ] Implement `batch_get_messages(creds, ids)`: chunk into groups of 100, use Gmail batch HTTP endpoint, parse `sender_address`, `sender_domain`, `display_name`, `subject`, `date`, `labels`, `has_unsubscribe`
- [ ] Implement `batch_delete(creds, ids)`: call `messages.batchDelete`, return `BatchDeleteResult(deleted, failed)`
- [ ] Implement retry logic: catch 429 and 5xx, exponential backoff, max 3 retries, raise `GmailAPIError` on exhaustion

**Covers:** REQ-007, REQ-008, REQ-011, REQ-022, REQ-025, REQ-040

---

### 6. Sync Service

- [ ] Create `backend/sync.py` — `run_sync(creds, db)`: orchestrates `list_message_ids` → `batch_get_messages` → wipe `emails` table → `upsert_emails` → update `sync_state`
- [ ] Add in-memory `is_syncing` flag on FastAPI app state; set on sync start, clear on terminal state
- [ ] On sync failure after retries: preserve existing `emails` table, mark `sync_state` as `sync_failed`

**Covers:** REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012

---

### 7. Heuristic Classifier

- [ ] Create `backend/classifier.py` — define `SIGNALS` dict and `DELETION_THRESHOLD = 60`
- [ ] Define `SENDER_PATTERNS` list: `no-reply`, `noreply`, `newsletter`, `marketing`, `mailer`, `donotreply`, `notifications`, `updates`, `news`, `info`, `hello`, `team`, `alerts`
- [ ] Implement `classify_emails(emails)`: score each record, return `list[ClassificationResult]` sorted by score descending
- [ ] Ensure classifier reads only from the passed `EmailRecord` list — no DB calls

**Covers:** REQ-013, REQ-014

---

### 8. Sender Rules Engine

- [ ] Create `backend/sender_rules.py` — `resolve_candidates(db, classifications)`: apply `delete`/`protect` rules on top of heuristic scores, return final ordered list
- [ ] Implement `protect` wins on conflict (sender present in both rule types)
- [ ] Implement `derive_rules_from_deletion(db, deleted_ids, protected_ids)`: upsert `auto` rules; skip any `manual` rules
- [ ] Implement `add_manual_rule(db, sender_address, rule, display_name)`: upsert with `source='manual'`
- [ ] Implement `delete_rule(db, sender_address)`: remove rule, revert to heuristic scoring

**Covers:** REQ-015, REQ-016, REQ-026, REQ-027, REQ-028, REQ-030, REQ-031, REQ-032

---

### 9. Deletion Service

- [ ] Create `backend/deletion.py` — `delete_emails(creds, db, deleted_ids, protected_ids)`:
  - Call `batch_delete(creds, deleted_ids)`
  - Remove successfully deleted IDs from `emails` table
  - Call `derive_rules_from_deletion(db, deleted_ids, protected_ids)`
  - Return `DeleteResponse(deleted, failed)`
- [ ] On DB write failure during rule derivation: log error, return deletion result normally, set `rules_saved=False` in response

**Covers:** REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-029

---

### 10. API Router

- [ ] Create `backend/main.py` — FastAPI app bound to `127.0.0.1` only
- [ ] `GET /api/auth/status` — returns `{ authenticated: bool }`
- [ ] `GET /api/auth/start` — triggers OAuth flow, returns redirect
- [ ] `GET /api/auth/callback` — handles OAuth code exchange
- [ ] `DELETE /api/auth` — calls `revoke_credentials()`
- [ ] `POST /api/sync` — starts sync if not already syncing; returns `SyncStatusResponse`
- [ ] `GET /api/sync/status` — returns current `SyncStatusResponse`
- [ ] `GET /api/review` — runs classifier + rule resolution, returns `ReviewResponse`
- [ ] `POST /api/delete` — accepts `DeleteRequest(deleted_ids, protected_ids)`; blocks if sync or delete in progress; returns `DeleteResponse`
- [ ] `GET /api/rules` — returns all sender rules ordered by `updated_at` DESC
- [ ] `POST /api/rules` — upserts a manual sender rule
- [ ] `DELETE /api/rules/{sender_address}` — removes a sender rule
- [ ] Add CORS middleware restricted to `http://localhost:5173`
- [ ] Add in-memory `is_deleting` flag; set on delete start, clear on terminal state

**Covers:** REQ-001, REQ-010, REQ-021, REQ-033, REQ-034, REQ-035, REQ-036, REQ-039

---

### 11. Frontend — App Shell

- [ ] Create `frontend/src/App.tsx` — SPA shell with sidebar nav: Review, Sender Rules
- [ ] Create `frontend/src/api.ts` — typed fetch wrappers for all backend endpoints
- [ ] Implement auth guard: on load, call `GET /api/auth/status`; redirect to Connect screen if unauthenticated
- [ ] Create `frontend/src/views/Connect.tsx` — "Connect Gmail" screen with connect button

**Covers:** REQ-001, REQ-002, REQ-003, REQ-004

---

### 12. Frontend — Review View

- [ ] Create `frontend/src/views/Review.tsx` — fetch `GET /api/review` on mount; render table of deletion candidates
- [ ] Each row: sender display name, sender address, subject, date, reason tag ("Learned rule" / "Promotional signals")
- [ ] All rows pre-selected by default; checkbox per row for deselection
- [ ] "Delete X emails" button updates count reactively as rows are deselected
- [ ] Confirmation dialog: "Permanently delete X emails?" with Cancel / Confirm
- [ ] WHILE deletion is in progress: disable Delete button, disable Re-sync button, show progress indicator
- [ ] On completion: show result summary (deleted count, failed IDs if any)
- [ ] On completion: show Re-sync button (enabled only after deletion reaches terminal state)
- [ ] IF candidate list is empty: show "No promotional emails detected" message with link to Sender Rules

**Covers:** REQ-017, REQ-018, REQ-019, REQ-020, REQ-021, REQ-024, REQ-025, REQ-034, REQ-035, REQ-036

---

### 13. Frontend — Sender Rules View

- [ ] Create `frontend/src/views/SenderRules.tsx` — fetch `GET /api/rules` on mount; render table ordered by `updated_at` DESC
- [ ] Each row: display name, sender address, rule type badge (`delete` / `protect`), source badge (`auto` / `manual`), remove button
- [ ] Add sender form: input for sender address, rule type toggle, optional display name, submit calls `POST /api/rules`
- [ ] Remove button calls `DELETE /api/rules/{sender_address}` with confirmation prompt
- [ ] Edit rule type in-place: clicking the rule badge toggles and calls `POST /api/rules` with updated rule

**Covers:** REQ-030, REQ-031, REQ-032, REQ-033

---

### 14. Tests

> **Rule: No real API calls in any test.** All Google OAuth and Gmail API interactions must be mocked. Backend tests use `unittest.mock.patch` to replace `google-auth-oauthlib` and `google-api-python-client` calls. Frontend tests use `msw` (Mock Service Worker) to intercept all `fetch` calls to the backend. No test may trigger a real network request.

- [ ] Create `backend/tests/conftest.py` — shared pytest fixtures: in-memory SQLite DB, mock `Credentials` object, mock Gmail API service factory
- [ ] Create `backend/tests/test_auth.py` — mock `google_auth_oauthlib.flow` and `google.oauth2.credentials`; test token load, auto-refresh, revoke, `OAuthError` on denied consent
- [ ] Create `backend/tests/test_gmail_client.py` — mock Gmail API service; test retry logic on mocked 429/5xx responses, batch chunking at 100-ID boundary, `batch_delete` partial failure response parsing
- [ ] Create `backend/tests/test_classifier.py` — pure unit tests (no mocks needed); test each signal weight, score 59 vs 60 threshold boundary, overlapping signals, empty email list
- [ ] Create `backend/tests/test_sender_rules.py` — use in-memory SQLite fixture; test `resolve_candidates` (delete override, protect override, protect-wins-on-conflict), `derive_rules_from_deletion` (auto rule upsert, manual rule not overwritten)
- [ ] Create `backend/tests/test_deletion.py` — mock `batch_delete`; test successful deletion removes IDs from DB, partial failure still processes successes, rule derivation DB failure returns warning without failing deletion
- [ ] Create `backend/tests/test_sync.py` — mock `list_message_ids` and `batch_get_messages`; test sync state transitions, emails table replacement, failure preserves previous cache contents
- [ ] Create `backend/tests/test_api.py` — FastAPI `TestClient`; mock `gmail_client` module entirely; test all 12 routes including auth guard, sync-in-progress blocking, delete-in-progress blocking
- [ ] Add `msw` to `frontend/` dev dependencies; create `frontend/src/tests/mocks/handlers.ts` — MSW request handlers for all backend endpoints
- [ ] Create `frontend/src/tests/Review.test.tsx` — MSW intercepts backend calls; test pre-selection, deselection count update, delete button and Re-sync button disabled states during deletion, result summary rendering, empty state message
- [ ] Create `frontend/src/tests/SenderRules.test.tsx` — MSW intercepts backend calls; test rule list rendering, add rule form submission, remove rule confirmation, in-place rule type edit

**Covers:** All REQ-001 through REQ-040 (see coverage map below)

---

## Test Coverage Map

| Requirement | Description | Test file(s) | Type |
|---|---|---|---|
| REQ-001 | No token → Connect screen, all views blocked | `test_api.py`, `Review.test.tsx` | integration, component |
| REQ-002 | Connect Gmail opens OAuth consent | `test_auth.py` | unit |
| REQ-003 | Callback exchanges code, saves token chmod 600 | `test_auth.py` | unit |
| REQ-004 | Denied consent → error, back to Connect screen | `test_auth.py`, `Review.test.tsx` | unit, component |
| REQ-005 | Expired token auto-refreshes silently | `test_auth.py` | unit |
| REQ-006 | Refresh failure → invalidate token, Reconnect prompt | `test_auth.py`, `test_api.py` | unit, integration |
| REQ-007 | Sync fetches 1,000 IDs newest-first | `test_sync.py` | unit |
| REQ-008 | Metadata fetched in batches of ≤100 | `test_gmail_client.py` | unit |
| REQ-009 | Successful sync replaces emails table, updates sync_state | `test_sync.py` | unit |
| REQ-010 | Progress indicator shown, second sync blocked while syncing | `test_api.py`, `Review.test.tsx` | integration, component |
| REQ-011 | 429/5xx retried up to 3x with backoff | `test_gmail_client.py` | unit |
| REQ-012 | Sync failure preserves previous cache, marks sync_failed | `test_sync.py` | unit |
| REQ-013 | All 6 signals scored correctly per email | `test_classifier.py` | unit |
| REQ-014 | Score ≥60 flagged, score 59 not flagged | `test_classifier.py` | unit |
| REQ-015 | delete rule overrides low score; protect rule overrides high score | `test_sender_rules.py` | unit |
| REQ-016 | Both rules present → protect wins | `test_sender_rules.py` | unit |
| REQ-017 | Review screen shows sender, subject, date per row | `Review.test.tsx` | component |
| REQ-018 | All candidates pre-selected by default | `Review.test.tsx` | component |
| REQ-019 | Deselecting a row removes it from pending set only | `Review.test.tsx` | component |
| REQ-020 | Delete button shows confirmation with exact count | `Review.test.tsx` | component |
| REQ-021 | Empty candidate list shows detection message + rules link | `Review.test.tsx` | component |
| REQ-022 | Confirmed deletion calls batchDelete with all IDs | `test_deletion.py` | unit |
| REQ-023 | Deleted IDs removed from emails table | `test_deletion.py` | unit |
| REQ-024 | Result summary shows deleted count and failed IDs | `Review.test.tsx` | component |
| REQ-025 | Partial batchDelete failure: successes processed, failures shown | `test_deletion.py`, `Review.test.tsx` | unit, component |
| REQ-026 | Deleted senders get auto delete rule | `test_sender_rules.py` | unit |
| REQ-027 | Deselected senders get auto protect rule | `test_sender_rules.py` | unit |
| REQ-028 | Auto derivation does not overwrite manual rules | `test_sender_rules.py` | unit |
| REQ-029 | Rule derivation DB failure: deletion completes, warning returned | `test_deletion.py` | unit |
| REQ-030 | Manual rule added via UI, applied on next review load | `test_api.py`, `SenderRules.test.tsx` | integration, component |
| REQ-031 | Rule removed, sender reverts to heuristic on next review | `test_api.py`, `SenderRules.test.tsx` | integration, component |
| REQ-032 | Rule edit updates rule and sets source=manual, updated_at | `test_sender_rules.py`, `SenderRules.test.tsx` | unit, component |
| REQ-033 | Rules displayed ordered by updated_at DESC with type and source | `SenderRules.test.tsx` | component |
| REQ-034 | Re-sync button appears only after deletion reaches terminal state | `Review.test.tsx` | component |
| REQ-035 | Re-sync button disabled while deletion is in progress | `Review.test.tsx` | component |
| REQ-036 | Re-sync applies updated rules when generating new candidates | `test_sync.py`, `test_sender_rules.py` | unit |
| REQ-037 | token.json created with chmod 600 | `test_auth.py` | unit |
| REQ-038 | No email body content written to disk at any point | `test_gmail_client.py`, `test_sync.py` | unit |
| REQ-039 | Server binds to 127.0.0.1 only | `test_api.py` | integration |
| REQ-040 | No requests to destinations outside googleapis.com / accounts.google.com | `test_gmail_client.py`, `test_auth.py` | unit |

---

## Definition of Done

- [ ] All implementation task checkboxes above are checked
- [ ] All tests in the coverage map pass
- [ ] No new linter warnings or type errors (`pylint` / `tsc --noEmit`)
- [ ] No test makes a real network request — confirmed by running the test suite with network access disabled (e.g., `pytest --no-network` or equivalent)
- [ ] App starts cleanly from a fresh clone following `SETUP.md`
- [ ] OAuth flow completes end-to-end with a real Google account
- [ ] Sync, review, delete, and re-sync complete without errors on a real Gmail inbox
- [ ] `token.json` confirmed to have permissions `600` after auth
- [ ] No email body content present in SQLite cache (verified by inspecting `emails` table)
- [ ] Server confirmed to reject connections from any interface other than `127.0.0.1`

---

## Risks and Open Questions

| # | Risk / Question | Status |
|---|---|---|
| 1 | Gmail API batch HTTP response parsing is non-trivial (multipart MIME). `google-api-python-client` handles this, but partial failures within a batch need per-item error checking. | Open |
| 2 | Google OAuth consent screen requires the app to be in "Testing" mode with the user's Gmail address added as a test user. First-time users may be confused by the "unverified app" warning. `SETUP.md` covers this but may need a UI hint as well. | Open |
| 3 | Heuristic classifier threshold (60) is a starting estimate. May produce too many false positives or negatives until sender rules are populated. Consider making the threshold configurable in `.env`. | Open |
| 4 | `batchDelete` permanently deletes emails — there is no undo. The confirmation dialog (REQ-020) is the only safeguard. Consider whether a "move to trash" option should be offered as a safer default. | Open |

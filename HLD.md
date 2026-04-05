# Gmail Cleanup Tool — High Level Design

## Problem Statement

Users accumulate large volumes of unwanted email (newsletters, promotions, automated notifications) that Gmail's native UI is too slow and manual to clean up effectively. There is no locally-hosted tool that lets a user quickly load, filter, review, and bulk-delete emails with full control and no data leaving their machine.

---

## Scope

**In scope:**
- Local web app (backend + frontend) running on the user's machine
- Gmail OAuth 2.0 authentication using the user's own Google Cloud credentials
- Load the most recent 1,000 emails from Gmail per session
- After a deletion pass, the user can refresh/re-sync to load the next 1,000 most recent emails for additional cleanup sessions
- Filter emails by sender, domain, subject keyword, date range, label, attachment presence, read status
- Sender analysis view (grouped by sender with counts)
- Deletion review screen — user scans a list (sender / subject / date) and deselects before confirming
- Bulk permanent delete via Gmail `batchDelete` (up to 1,000 IDs per call)
- Secondary bulk actions: trash, archive, mark read/unread, label management
- Unsubscribe helper (detect `List-Unsubscribe` headers, surface one-click links)
- Local SQLite cache for email metadata

**Out of scope:**
- Cloud hosting or multi-user support
- Email composition or sending
- Non-Gmail accounts
- Scheduled / automated cleanup rules
- Mobile support

---

## Components Affected

This is a greenfield project — no existing modules.

---

## New Components

| Component | Responsibility |
|---|---|
| **Auth Service** | OAuth 2.0 flow, token storage/refresh, scope management |
| **Gmail Sync Service** | Fetches the most recent 1,000 emails from Gmail API; paginates via `messages.list` + `messages.get` (batch) |
| **Local Cache (SQLite)** | Stores email metadata (id, sender, subject, date, labels, has_attachment, unsubscribe header); invalidated on sync |
| **Filter Engine** | Applies user-defined filters against the cache and returns matching message IDs |
| **Deletion Service** | Accepts a list of message IDs; calls `batchDelete` in chunks of ≤1,000; reports progress |
| **Heuristic Classifier** | Scores each email for promotional likelihood using local signals; no external API calls |
| **Sender Rules Engine** | Manages a persistent `sender_rules` table (`delete` / `protect`); derives rules from user deletion actions; supports manual additions |
| **Unsubscribe Service** | Parses `List-Unsubscribe` headers from cached metadata; exposes mailto/HTTP links |
| **FastAPI Backend** | REST API layer exposing all services to the frontend |
| **React Frontend** | SPA — Inbox Overview, Sender Analysis, Smart Filters, Deletion Review, Unsubscribe Helper |

---

## External Interfaces

- **Gmail API** — `messages.list`, `messages.batchGet`, `messages.batchDelete`, `users.getProfile`
- **Google OAuth 2.0** — authorization code flow with PKCE, scopes: `gmail.modify`
- **Local REST API** — consumed only by the local frontend (no external exposure)

---

## Key Constraints

- **API rate limits** — Gmail API has per-user quotas (250 quota units/second). `batchGet` and `batchDelete` must be throttled. Prefer fewer, larger calls over many small ones.
- **Privacy** — No email body content is stored on disk. Metadata only in cache.
- **Token security** — OAuth tokens stored at `~/.gmail-cleanup/token.json` with `chmod 600`.
- **Inbox size** — Hard cap of 1,000 most recent emails loaded per session to keep UX fast and API usage bounded. After completing a deletion pass, the user can refresh/re-sync to load the next 1,000 most recent emails for continued cleanup across multiple sessions.
- **Classification is local-only** — No external APIs for sender scoring. All classification uses signals present in the cached metadata (Gmail labels, headers, sender address patterns). Accuracy improves over sessions via the sender rules table.
- **Single user** — No authentication layer on the local server itself; it binds to `localhost` only.

---

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Pure CLI tool (no UI)** | Deletion of emails requires visual review of sender/subject before confirming — a CLI table is too slow to scan and deselect from |
| **Browser extension** | Requires publishing to a store, more complex auth, and tighter coupling to Gmail's DOM changes |
| **Load all emails (no cap)** | Accounts with 50k+ emails would cause unacceptable API quota usage and slow load times. The 1,000-per-session model with easy re-sync supports iterative cleanup without sacrificing performance |
| **No local cache (always fetch live)** | Filtering and sender grouping require iterating over all 1,000 emails repeatedly; caching metadata makes this instant |
| **LLM-based sender classification** | Would better understand semantic context (e.g., "Zillow" vs. "lease renewal") but introduces an external API dependency, requires an API key, and fails offline. Local heuristics + user-confirmed sender rules close the gap over time without any external calls |

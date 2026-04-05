# Gmail Cleanup Tool — Product Specification

## Overview

A locally hosted web application that connects to a user's Gmail account via OAuth and provides tools to bulk-manage, filter, and clean up emails. The application runs entirely on the user's machine — no data is sent to any third-party server beyond the Gmail API.

---

## Goals

- Allow users to quickly identify and delete unwanted emails (newsletters, promotions, spam, etc.)
- Provide filtering and search capabilities beyond what Gmail's native UI offers
- Operate locally to keep credentials and email data private
- Be fast and usable for inboxes with tens of thousands of emails
- Avoid throttling the Gmail API - we want to prioritize less errors for this API call
- A user friendly UI that is easy to navigate and use

---

## Non-Goals

- No cloud deployment or multi-user support
- No email composition or sending
- No support for non-Gmail accounts (at launch)

---

## Tech Stack

| Layer       | Technology              |
|-------------|-------------------------|
| Backend     | Python (FastAPI)        |
| Frontend    | React + Tailwind CSS    |
| Auth        | Google OAuth 2.0        |
| Gmail API   | Google Gmail REST API   |
| Storage     | Local SQLite (cache)    |

> Adjust the tech stack above to match your preferences.

---

## Authentication

- User authenticates via Google OAuth 2.0 using their own Google Cloud project credentials
- OAuth tokens are stored locally (e.g., `~/.gmail-cleanup/token.json`)
- Scopes required:
  - `https://www.googleapis.com/auth/gmail.modify` — read and delete emails
  - `https://www.googleapis.com/auth/gmail.readonly` — (optional, read-only mode)
- Batch delete support: the Gmail API's `batchDelete` endpoint allows deleting up to 1,000 message IDs in a single request — this is the preferred deletion method to minimize API calls and reduce throttling risk
- First-time setup flow: user provides their `client_id` and `client_secret` via a config file or setup wizard

---

## Core Features

### 1. Inbox Overview
- Load only the most recent 1,000 emails to keep performance predictable and avoid overloading the API
- After a deletion pass, the user can refresh/re-sync to load the next 1,000 most recent emails for additional cleanup sessions
- Display count and breakdown of loaded emails by category (Promotions, Social, Updates, Spam, etc.)
- Unread count and storage usage displayed as summary stats

### 2. Sender Analysis
- List all unique senders sorted by email count
- Show total email count and date range per sender
- Allow bulk-select and delete by sender

### 3. Smart Filters
- Filter emails by:
  - Sender domain or address
  - Subject keyword
  - Date range
  - Has attachment
  - Label / category
  - Read/unread status
- Preview filtered results before deletion

### 4. Predictive Sender Classification
- On each sync, every email is scored for "promotional likelihood" using local heuristics — no external API calls
- Scoring signals (cumulative):
  - `List-Unsubscribe` header present → strong promotional indicator
  - Gmail label is `CATEGORY_PROMOTIONS` or `CATEGORY_UPDATES` → strong promotional indicator
  - Sender address matches known patterns (`no-reply`, `noreply`, `newsletter`, `marketing`, `mailer`, `donotreply`, `notifications`, `updates`, `news`) → moderate indicator
  - Gmail label is `IMPORTANT` or `STARRED` → strong protective indicator (suppresses deletion suggestion)
- Emails scoring above a promotional threshold are pre-selected for deletion in the review screen
- Learned sender rules (see Feature 7) override heuristic scores entirely

### 5. Deletion Review & Confirm
- Before any deletion is executed, the user is shown a full list of emails pre-selected for deletion
- Each row displays: sender, subject line, and date — no body content needed
- Pre-selected list is generated from heuristic scores + learned sender rules
- User can deselect individual emails from the list before confirming
- A final confirm action triggers the bulk delete (using `batchDelete`, up to 1,000 per request)
- Progress indicator shown during deletion
- After deletion completes, sender rules are automatically derived from the user's choices (see Feature 7)

### 6. Sender Rules (Persistent Memory)
- After each confirmed deletion, the tool automatically records sender rules:
  - Senders whose emails were **deleted** → flagged as `delete` (pre-selected in all future sessions)
  - Senders whose emails were **deselected** by the user → flagged as `protect` (never pre-selected)
- Users can also manually manage the sender rules list from the UI:
  - Add any sender address or domain to the `delete` list (e.g., typing "ESPN" adds all emails from that sender)
  - Add any sender to the `protect` list
  - Remove or edit existing rules
- Rules persist in SQLite across sessions and survive re-syncs
- `delete` rules take priority in pre-selection; `protect` rules are always excluded from the deletion list

### 7. Bulk Actions
- Primary action: permanently delete (via `batchDelete`)
- Secondary: move to trash, archive
- Mark as read / unread
- Apply/remove labels

### 8. Unsubscribe Helper
- Detect emails with `List-Unsubscribe` headers
- Display a list of subscription senders
- One-click unsubscribe (via mailto or HTTP link)

---

## Data Flow

```
User Browser → Local Frontend (React)
                    ↓
           Local Backend (FastAPI)
                    ↓
           Gmail API (Google)
```

All API calls are made from the local backend. The frontend never talks to Gmail directly.

---

## Local Cache

- Email metadata (IDs, senders, subjects, dates) is cached in a local SQLite database
- Cache is refreshed on demand or on a configurable sync interval
- Full email bodies are fetched on demand, not cached

---

## Configuration

A `config.yaml` (or `.env`) file stores:
- `client_id` / `client_secret` — Google OAuth credentials
- `port` — local server port (default: `8080`)
- `sync_batch_size` — number of emails to fetch per API call (default: `500`)
- `cache_path` — path to local SQLite cache

---

## UI/UX Requirements

- Single-page application with a sidebar for navigation
- Responsive but optimized for desktop
- Confirmation dialogs before any destructive bulk action
- Progress indicators for long-running operations (sync, bulk delete)
- Dark mode support

---

## Security Considerations

- OAuth tokens stored with restricted file permissions (`chmod 600`)
- No email content logged to disk
- All network traffic goes directly to `googleapis.com`
- Option to revoke access and clear local cache from the UI

---

## Out of Scope (Future Considerations)

- Scheduled / automated cleanup rules
- Support for other email providers (Outlook, Yahoo)
- Browser extension variant
- Mobile support

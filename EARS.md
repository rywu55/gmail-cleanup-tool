# Gmail Cleanup Tool — EARS Requirements

## Authentication

**REQ-001:** WHEN the application starts and no valid `token.json` exists, the system shall display a "Connect Gmail" screen and prevent access to all other views.

**REQ-002:** WHEN the user clicks "Connect Gmail", the system shall open a browser window to the Google OAuth consent screen requesting the `gmail.modify` scope.

**REQ-003:** WHEN Google redirects to the localhost callback with a valid authorization code, the system shall exchange the code for tokens, save them to `~/.gmail-cleanup/token.json` with permissions `600`, and redirect the user to the main view.

**REQ-004:** IF the user denies OAuth consent or the OAuth flow returns an error, THEN the system shall display an error message and return the user to the "Connect Gmail" screen.

**REQ-005:** WHEN an API call is made and the access token is expired, the system shall automatically refresh the token using the stored refresh token without requiring user action.

**REQ-006:** IF the token refresh request fails, THEN the system shall invalidate the local token, display a "Reconnect Gmail" prompt, and block all further API calls until re-authentication completes.

---

## Sync

**REQ-007:** WHEN the user triggers a sync, the system shall fetch the most recent 1,000 message IDs from Gmail ordered newest-first.

**REQ-008:** WHEN fetching message metadata, the system shall request messages in batches of no more than 100 per batch HTTP request.

**REQ-009:** WHEN a sync completes successfully, the system shall replace the entire `emails` table with the newly fetched records and update `sync_state.last_synced_at`.

**REQ-010:** WHILE a sync is in progress, the system shall display a progress indicator and prevent the user from triggering a second sync.

**REQ-011:** IF a Gmail API request during sync returns a 429 or 5xx response, THEN the system shall retry that request up to 3 times with exponential backoff before marking the sync as failed.

**REQ-012:** IF a sync fails after all retries are exhausted, THEN the system shall preserve the previous `emails` table contents, mark sync state as `sync_failed`, and display an error with a retry option.

---

## Classification

**REQ-013:** WHEN a sync completes, the system shall score every fetched email using the following local signals: presence of `List-Unsubscribe` header (+40), Gmail label `CATEGORY_PROMOTIONS` (+35), Gmail label `CATEGORY_UPDATES` (+20), sender address matching a known promotional pattern (+20), Gmail label `IMPORTANT` (-50), Gmail label `STARRED` (-60).

**REQ-014:** The system shall flag any email with a cumulative score of 60 or above as a deletion candidate.

**REQ-015:** WHEN resolving deletion candidates, the system shall apply sender rules after heuristic scoring: emails from a sender with a `delete` rule shall be flagged regardless of score; emails from a sender with a `protect` rule shall be excluded regardless of score.

**REQ-016:** WHEN a sender has both a `delete` and `protect` rule, the system shall apply the `protect` rule and exclude the email from the deletion candidates.

---

## Deletion Review

**REQ-017:** WHEN the user navigates to the Review screen, the system shall display all deletion candidates as a list with one row per email showing: sender display name, sender address, subject, and date.

**REQ-018:** The system shall pre-select all deletion candidates for deletion by default on the Review screen.

**REQ-019:** WHEN the user deselects a row on the Review screen, the system shall remove that email from the pending deletion set without affecting other rows.

**REQ-020:** WHEN the user clicks "Delete", the system shall display a confirmation dialog stating the exact number of emails to be permanently deleted before executing any deletion.

**REQ-021:** IF the deletion candidate list is empty after classification and rule resolution, THEN the system shall display a message indicating no promotional emails were detected and prompt the user to add senders manually.

---

## Deletion Execution

**REQ-022:** WHEN the user confirms deletion, the system shall call Gmail `batchDelete` with all confirmed message IDs in a single request.

**REQ-023:** WHEN deletion completes, the system shall remove all successfully deleted message IDs from the local `emails` table.

**REQ-024:** WHEN deletion completes, the system shall display a result summary showing the count of successfully deleted emails and the count of any failed IDs.

**REQ-025:** IF `batchDelete` returns failures for one or more message IDs, THEN the system shall still process all successful deletions and display the failed IDs to the user.

---

## Sender Rule Derivation

**REQ-026:** WHEN a deletion pass completes, the system shall upsert a `delete` rule (source `auto`) for every unique sender address present in the confirmed deletion set.

**REQ-027:** WHEN a deletion pass completes, the system shall upsert a `protect` rule (source `auto`) for every unique sender address present in the user's deselected set.

**REQ-028:** WHEN deriving rules automatically, the system shall not overwrite any existing rule with source `manual`.

**REQ-029:** IF rule derivation fails due to a database error, THEN the system shall complete the deletion response normally and display a non-blocking warning that sender rules were not saved.

---

## Sender Rules Management

**REQ-030:** WHEN the user adds a sender address via the Sender Rules UI, the system shall upsert the rule with source `manual` and apply it on the next review load.

**REQ-031:** WHEN the user removes a sender rule, the system shall delete the rule from `sender_rules` and revert that sender to heuristic-only scoring on the next review load.

**REQ-032:** WHEN the user edits a rule (e.g., flipping `delete` to `protect`), the system shall update the rule with source `manual` and `updated_at` set to the current timestamp.

**REQ-033:** The system shall display all sender rules in the Sender Rules UI ordered by `updated_at` descending, showing the rule type, source (`auto` / `manual`), and display name.

---

## Re-sync for Next Batch

**REQ-034:** WHEN a deletion pass completes and all `batchDelete` requests have returned a final result (success or failure), the system shall display a "Re-sync" button to load the next batch of emails.

**REQ-035:** WHILE a deletion is in progress, the system shall disable the Re-sync button and prevent any sync from being triggered until the deletion reaches a terminal state (all IDs either deleted or failed).

**REQ-036:** WHEN a re-sync completes, the system shall immediately apply the updated sender rules (including any newly derived from the previous deletion pass) when generating the new deletion candidate list.

---

## Non-Functional

**REQ-037:** The system shall bind the local server exclusively to `127.0.0.1` and shall not accept connections from any other network interface.

**REQ-038:** The system shall store OAuth tokens at `~/.gmail-cleanup/token.json` with file permissions set to `600` at the time of creation.

**REQ-039:** The system shall not write any email body content to disk at any point.

**REQ-040:** The system shall not make any network requests to destinations other than `accounts.google.com` and `www.googleapis.com`.

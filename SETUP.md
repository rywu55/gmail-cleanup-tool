# Gmail Cleanup Tool — Setup Guide

## Prerequisites

Before starting, ensure the following are installed on your machine:

| Tool | Minimum Version | Check |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

---

## Step 1 — Create a Google Cloud Project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Give it a name (e.g., `gmail-cleanup`) and click **Create**
4. Make sure the new project is selected in the dropdown before continuing

---

## Step 2 — Enable the Gmail API

1. In the left sidebar go to **APIs & Services → Library**
2. Search for **Gmail API**
3. Click it and press **Enable**

---

## Step 3 — Configure the OAuth Consent Screen

Google has reorganized this UI. There are now three variants depending on when your project was created:

**Newest UI (Overview page with sidebar sections):**
1. Go to **APIs & Services → OAuth consent screen** — you land on an Overview page
2. In the left sidebar, click **Audience**
3. Select **External** and click **Save**
   > For personal Gmail accounts, External is the only option. If you see Internal, your account is a Google Workspace account — select Internal and skip the test users step.
4. In the left sidebar, click **Branding**
5. Fill in **App name** (e.g., `Gmail Cleanup Tool`) and **User support email**, then save
6. In the left sidebar, click **Data Access**
7. Click **Add or remove scopes**, search for `https://mail.google.com/`, check it, and click **Update** then **Save**
   > **This step is required.** If the scope is not added here, Google will not grant it during the OAuth flow even if the code requests it.
8. In the left sidebar, click **Audience** again and scroll to **Test users**
9. Click **Add users** and add your own Gmail address — this allows you to authenticate while the app is in Testing mode

**If you see a "Get started" button:**
1. Click **Get started**
2. Fill in **App name** and **User support email**
3. Under **Audience**, select **External**
4. Complete the flow, then add yourself as a test user on the Audience page

**Older UI (External / Internal radio buttons on first load):**
1. Select **External** and click **Create**
2. Fill in App name, User support email, Developer contact email
3. Click **Save and Continue** through Scopes
4. On the **Test Users** screen, add your Gmail address
5. Click **Save and Continue** then **Back to Dashboard**

---

## Step 4 — Create OAuth 2.0 Credentials

**Newest UI:**
1. In the left sidebar under **APIs & Services → OAuth consent screen**, click **Clients**
2. Click **+ Create client**
3. Set **Application type** to **Desktop app**
4. Give it a name (e.g., `gmail-cleanup-local`) and click **Create**
5. Copy the **Client ID** and **Client Secret** from the dialog that appears

**Older UI:**
1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Set **Application type** to **Desktop app**
4. Give it a name and click **Create**
5. Copy the **Client ID** and **Client Secret** from the dialog that appears

---

## Step 5 — Configure the Application

In the project root, create a `.env` file:

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```env
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
PORT=8080
```

> Never commit `.env` to version control. It is already listed in `.gitignore`.

---

## Step 6 — Install Backend Dependencies

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 7 — Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## Step 8 — Run the Application

Open two terminal windows:

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open your browser and go to:
```
http://localhost:5173
```

---

## Step 9 — Connect Your Gmail Account

1. On first load you will see the **Connect Gmail** screen
2. Click **Connect Gmail** — your browser will open a Google consent screen
3. Select your Google account and click **Allow**
4. You will be redirected back to the app automatically
5. The app will begin syncing your most recent 200 emails

> Your OAuth token is saved locally at `~/.gmail-cleanup/token.json` and is never sent anywhere other than Google's servers.

---

## Troubleshooting

**"Access blocked: this app has not been verified by Google"**
This appears because the app is in Testing mode. Click **Advanced → Go to [app name] (unsafe)** to proceed. This is expected for a personal local tool that has not been submitted for Google verification.

**"Error 400: redirect_uri_mismatch"**
The redirect URI in your Google Cloud credentials does not match what the app expects. Ensure your OAuth client type is set to **Desktop app**, not Web application.

**"Token refresh failed / Reconnect Gmail"**
Your refresh token has expired or been revoked. Click **Reconnect Gmail** and go through the OAuth flow again. This also happens if you revoke access via your Google account permissions page.

**"Request had insufficient authentication scopes" / all emails fail to delete**
The OAuth token was granted without the required Gmail scope. This usually means the scope was not added in Google Cloud Console before authenticating. Follow these steps to fix it:

1. Go to Google Cloud Console → **APIs & Services → OAuth consent screen → Data Access**
2. Click **Add or remove scopes**, find and add `https://mail.google.com/`, then save
3. Go to [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
4. Find **Gmail Cleanup Tool**, click it, and click **Delete** to confirm "Delete the connections you have with Gmail Cleanup Tool"
5. Delete the local token: `rm ~/.gmail-cleanup/token.json`
6. Restart the backend
7. Open the app and click **Connect Gmail** to re-authenticate

**Sync takes a long time**
The app fetches 200 emails in batches of 100. If your connection is slow or Google is rate-limiting, this may take a few seconds. The progress indicator will update throughout.

---

## Revoking Access

To disconnect the app from your Gmail account:

1. Go to [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
2. Find **Gmail Cleanup Tool**, click it, and click **Delete** to confirm
3. Delete the local token: `rm ~/.gmail-cleanup/token.json`

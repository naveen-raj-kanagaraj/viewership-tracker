# Sign in with Google: one-time setup (owner)

The code is deployed but stays off until the two keys below are in the server's `.env`. Nothing on the site is
locked and no Sign in button shows until then.

## 1. Create the Google login app (about 5 minutes)

1. Open https://console.cloud.google.com and sign in with the Google account that should own it (letsgrowesports).
2. Top bar: project picker, **New project**, name it `letsgrowesports`, Create, then select it.
3. Left menu: **Google Auth Platform** (or "APIs & Services > OAuth consent screen"), **Get started**:
   - App name: `letsgrowesports`; User support email: your email.
   - Audience: **External**.
   - Contact email: your email. Agree, **Create**.
4. **Branding** page:
   - Application home page: `https://live.letsgrowesports.com`
   - Privacy policy: `https://live.letsgrowesports.com/privacy`
   - Terms of service: `https://live.letsgrowesports.com/terms`
   - Authorised domains: `letsgrowesports.com`
   - Leave the logo empty for now (a logo makes Google review the brand first, which takes days). Save.
5. **Audience** page: **Publish app** (Testing mode lets only listed test users sign in). The site asks only for
   name, email and picture (`openid email profile`), which needs no Google review.
6. **Clients**, **Create client**:
   - Application type: **Web application**; Name: `live site`
   - Authorised JavaScript origins: `https://live.letsgrowesports.com`
   - Authorised redirect URIs: `https://live.letsgrowesports.com/auth/google/callback`
   - Create. Google shows a **Client ID** and **Client secret**. Keep that window open.

## 2. Put the keys on the server (your own Terminal, never in chat or git)

```
cd ~/Downloads/Projects/viewership-tracker && . ./.server && ssh -t -i "$KEY" ubuntu@$IP 'nano ~/viewership-tracker/.env'
```

Add two lines at the end (paste your own values), then Ctrl+O, Enter, Ctrl+X:

```
GOOGLE_CLIENT_ID=<the Client ID>
GOOGLE_CLIENT_SECRET=<the Client secret>
```

Restart:

```
cd ~/Downloads/Projects/viewership-tracker && . ./.server && ssh -i "$KEY" ubuntu@$IP 'sudo systemctl restart tracker && sleep 30 && systemctl is-active tracker'
```

## 3. Check

- https://live.letsgrowesports.com/global shows **Sign in** at the top right.
- Rankings show 25 rows with a "Sign in free" bar; after signing in, all of them.
- https://live.letsgrowesports.com/account shows your name, the weekly-report box, download and delete.

To switch it off again: add `SIGNIN=0` to `.env` and restart (accounts are kept).

## Where things are

- Accounts: `data/users.db` on the server (private, backed up nightly next to tracker.db as `backups/users-*.db`).
- Cookie signing key: `data/.session_key` (made on first start). Deleting it signs everyone out.
- Who asked for the weekly report: `auth.weekly_list()`; each email must carry `auth.unsub_link(id)`.
- Code: `tracker/auth.py`; locked APIs and limits: `auth.LOCKED_API`, `FREE_ROWS` (25), `FREE_DAYS` (7).

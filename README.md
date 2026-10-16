# Tambola Circle — Streamlit edition

A society Tambola game with a public player screen and a password-protected admin workspace. **Only the admin can draw a number.** There is no scheduler, OTP, player password, payment gateway, or automated payout.

## What is included

- Name/mobile join requests; manual host approval.
- A private, unguessable ticket link for each player, with host-controlled replacement/revocation.
- One standard 3×9, 15-number ticket per approved player per round.
- Host controls: approve/decline, allocate, start, pause, resume, draw, end, next round.
- Uniform random draws without repetition using Python's `secrets` module.
- Fixed Early five, Top line, Middle line, Bottom line, and Full house categories.
- Simultaneous winners detected on the same draw, with manual host confirmation.
- Manual marks for external money collection and prize distribution. No money is transferred.
- Number board, counts, ticket marking, activity history, previous rounds, private host export.
- Supabase PostgreSQL persistence in a private schema. SQLite is strictly an explicitly enabled local-demo/test option.
- Transactional draw/winner updates, stale-click protection, admin authorization at the service layer.

## Start here

The selected stack is **Supabase + GitHub + Streamlit Community Cloud**. Follow **DEPLOY.md** for hosted setup. The entrypoint is `app.py`; Python 3.12 is recommended. Dependencies are pinned in `requirements.txt`.

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/make_secrets.py
```

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`, replace the placeholders with your database connection and generated values, then:

```sh
streamlit run app.py
```

For a **local-only demonstration**, omit DATABASE_URL and add `TAMBOLA_DEMO = "1"`. You still need the generated admin password hash and SESSION_SECRET. This creates `demo.sqlite3` locally. Never enable this mode in Community Cloud.

## Tests

```sh
python -m unittest discover -s tests -v
```

Rules/service tests use disposable SQLite databases. UI tests use Streamlit AppTest, not a real browser. Production PostgreSQL connectivity and hosted concurrent load require verification against your connected database before inviting the society. There is no claim of a tested capacity of 200 concurrent players; 200 is a registration cap.

## Design and limits

- The player page refreshes every five seconds while open. The host dashboard refreshes after actions or with its Refresh button. A closed player page sends no refresh requests.
- A private ticket link grants access to that player's ticket. Players should bookmark it or save the link file. Opening only the group link in a new browser does **not** recover a ticket; ask the host for a replacement link. Replacement revokes the old link.
- Names/mobile numbers are not identity-verified. The host recognises and approves neighbours manually. Public registration can attract unwanted requests; decline them. Do not publish the group link broadly.
- Admin sessions expire after eight hours. Password failures are limited to ten in five minutes across the app. This simple shared limit may temporarily lock out the host during abuse.
- Change SESSION_SECRET to revoke existing admin sessions. Change ADMIN_PASSWORD_HASH and SESSION_SECRET together after a suspected password compromise.
- Players/tickets and prize categories cannot be changed after start. Host control does not include choosing drawn numbers or replacing winning tickets.
- New rounds preserve registrations and approvals but clear tickets and collection marks. Previous rounds are archived with player details and results.
- Host exports include mobile numbers and must stay private. Password hashes, access tokens, and database credentials are excluded.
- All shared game records live in one PostgreSQL row to keep mutations atomic and the implementation understandable for a small society. Very large groups/history require a normalized schema and load testing.
- Keep database backups using your provider. The host export is for records, not a full credential-preserving database restore.
- Existing Sites-game data is not imported. This Streamlit edition starts a new game and does not alter the earlier hosted site.

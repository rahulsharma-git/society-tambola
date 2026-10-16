# Deploy Tambola Circle

This package is ready for configuration and hosting; it is not already deployed to Streamlit.

## 1. Create the persistent database

Create a dedicated Supabase project on the Free plan. In the project dashboard, open **Connect → Session pooler** and copy its PostgreSQL URI. Use the session pooler on port **5432**, which supports IPv4. Do not use the Supabase project HTTP URL or an anon/publishable API key as DATABASE_URL.

Replace `[YOUR-PASSWORD]` in the connection URI with the database password, URL-encoding special characters. Preserve the exact username and hostname supplied by Supabase. Add `?sslmode=require` (or `&sslmode=require` if the URI already has a query string).

The app creates a `tambola_private` schema and its `tambola_state` table on first startup. It sets PostgreSQL search_path to that schema and revokes PUBLIC access to the schema. Keep **tambola_private out of Supabase’s exposed Data API schemas**. This server-side app does not use Supabase browser authentication or the REST Data API. A dedicated Supabase project is recommended because the initial database connection requires schema/table creation privileges.

The database password stays in Streamlit Secrets, never GitHub, browser code, player links, or a chat message. No live credentials are included in this package.

## 2. Choose your admin password

On a computer with Python 3.12, in this folder run:

```sh
python scripts/make_secrets.py
```

Choose a unique password of at least 12 characters. The script asks twice, then prints an admin password hash and a random SESSION_SECRET. Keep these values private. The app stores no plaintext admin password.

## 3. Put the code in your GitHub repository

Create/select a repository named, for example, `society-tambola`. Add the **contents of this folder** at its root, including `app.py`, `engine.py`, `storage.py`, `service.py`, `requirements.txt`, `.streamlit/config.toml`, the scripts and tests.

Do not upload `.streamlit/secrets.toml`, local database files, or a virtual environment. The included `.gitignore` excludes these. The example secrets file contains placeholders only and is safe to include.

## 4. Deploy in Streamlit Community Cloud

1. Sign in at https://share.streamlit.io/ using your GitHub account.
2. Create an app from the repository and branch you selected.
3. Set the entrypoint to `app.py` and Python version to 3.12.
4. Open Advanced settings / Secrets and add:

```toml
DATABASE_URL = "YOUR_POSTGRESQL_CONNECTION_URL"
ADMIN_PASSWORD_HASH = "OUTPUT_FROM_MAKE_SECRETS"
SESSION_SECRET = "OUTPUT_FROM_MAKE_SECRETS"
PUBLIC_APP_URL = "https://YOUR-CHOSEN-NAME.streamlit.app"
```

5. Deploy. Update PUBLIC_APP_URL if the final app URL differs.
6. Set the Streamlit app's viewing access to **public** so your friends are not asked to sign in. This is separate from repository visibility. The Admin workspace remains password-protected inside the app.
7. Leave `TAMBOLA_DEMO` unset. The app refuses SQLite outside explicit demo mode and does not silently fall back to local storage if PostgreSQL fails.

A public player page does not require a Streamlit, GitHub, Google, or ChatGPT account. Only you need hosting accounts. There is no new-player OTP or password.

## 5. Test before inviting the group

- Open the public URL in a private/incognito browser: it should show the player screen without a hosting sign-in wall.
- Join as a test player and save the private ticket link.
- In another browser, choose Admin and sign in using your chosen password.
- Approve the player and allocate tickets. Mark collection externally if applicable.
- Start the round. Confirm the player sees the same calls and automatically marked ticket numbers.
- Test Pause, Resume, and two admin tabs attempting to draw from the same displayed call. Only one of those stale concurrent clicks should advance the round.
- Reload both pages and verify records persist. Reopen the player's private link on another device.
- Test replacing a ticket link; the old link must stop resolving.
- End the test round and open a new round. Use a separate test database if you do not want test participants retained.

The packaged tests validate rules and service behavior locally, but are not a substitute for this hosted connectivity and browser check.

## 6. Run your society game

Share the **base app URL**, never an individual private ticket link, with the group. Approve neighbours after whatever manual checks you require. Allocate tickets before starting. Each click on Draw next number makes one random draw. Review winners in Prizes, confirm them, and mark distribution only after handling it yourself outside the app.

## Free hosting expectations

Streamlit Community Cloud offers free hosting and apps may sleep after inactivity; the next visitor may need to wait for startup. There are no background hourly draws to miss. Supabase Free has resource limits and projects can be paused under its current free-plan policy. Check the dashboard before game night. Five-second refreshing keeps the database active during play, so monitor usage and stop testing sessions when finished. Remaining within the free tier depends on actual use; this is not an unlimited-free-service guarantee.

Official references checked during preparation:
- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
- https://supabase.com/docs/guides/database/connecting-to-postgres

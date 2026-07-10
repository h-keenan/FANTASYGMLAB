# Development Workflow

`main` is deployable. Merging to `main` triggers Render auto-deploy.

Recommended branches:

- `codex/<task-name>`
- `fix/<issue-name>`
- `release/<version>`

Workflow:

1. Create a branch for the task.
2. Make focused changes.
3. Run:
   - `python -m compileall -q app.py modules`
   - `python -c "import app"`
   - `python -m pytest -q`
   - `python scripts/deployment_check.py` for deployment/config changes.
4. Push the branch.
5. Harry reviews before merge.
6. Merge to `main` only when the app is deployable.

Rules:

- Never commit real secrets.
- Never edit production environment variables from source code.
- Never put `SUPABASE_SERVICE_ROLE_KEY` in the Streamlit web service unless a reviewed server-only path requires it.
- Keep live Stripe billing disabled until a separate live-billing checklist is complete.
- Use Render environment variables for production configuration.
- Use `local_secrets/secrets.toml` for local-only values.

Emergency rollback:

1. Redeploy a previous Render commit.
2. Revert the bad Git commit.
3. Disable Render auto-deploy temporarily if repeated deploys are making recovery harder.
4. Restore environment variables from Render history or known-good notes if config caused the incident.

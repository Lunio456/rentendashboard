# RentenDashboard

Connect to bank accounts using OAuth 2.0 and display aggregated financial data in a console dashboard. Initially built against the Commerzbank Securities Sandbox, with secure local HTTPS callback and optional simulated auth for development.

## Features

- 🔐 OAuth 2.0 with local HTTPS callback (https://localhost:8443/callback)
- 🏦 Bank API integration (Commerzbank Securities Sandbox default)
- 📊 Aggregation of accounts, positions, and transactions
- 🖥️ Console dashboard output (Rich-style tables)
- � Saves raw portfolio JSONs to `artifacts/portfolio/`

## Prerequisites

- Python 3.10+ recommended
- Bank OAuth client (client_id/secret) or sandbox credentials

## Quick start

1) Clone and enter the repo

```bash
git clone https://github.com/Lunio456/rentendashboard.git
cd rentendashboard
```

2) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3) Install dependencies

```bash
pip install -r requirements.txt
```

4) Configure environment

```bash
cp .env.example .env
# Edit .env with your values (see below)
```

### .env keys

```env
# --- Bank OAuth (Commerzbank Sandbox defaults are pre-wired) ---
BANK_CLIENT_ID=your_client_id
BANK_CLIENT_SECRET=your_client_secret
BANK_REDIRECT_URI=https://localhost:8443/callback
BANK_API_BASE_URL=https://api-sandbox.commerzbank.com/securities-api/v4
BANK_AUTH_URL=https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/auth
BANK_TOKEN_URL=https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/token
BANK_SCOPE=

# Optional sandbox convenience (password grant)
BANK_USERNAME=
BANK_PASSWORD=

# --- Security ---
SECRET_KEY=change_me
# Optional: TOKEN_ENCRYPTION_KEY (32 bytes; if not base64, a Fernet key is derived)
TOKEN_ENCRYPTION_KEY=

# --- App / HTTPS callback ---
TLS_CERT_PATH=certs/dev-localhost.crt
TLS_KEY_PATH=certs/dev-localhost.key
LOG_LEVEL=INFO
```

Notes:
- If `BANK_CLIENT_ID/SECRET` and TLS certs are provided, the app uses the authorization code flow with a local HTTPS callback. Otherwise it falls back to a simulated token suitable for development.
- Ensure the exact redirect URI (https://localhost:8443/callback) is registered with your OAuth client.

## Run

```bash
python main.py
```

What happens:
1) OAuth flow starts (auth code flow if configured; otherwise simulated)
2) Accounts are fetched; for each account the portfolio (positions) is retrieved
3) Recent transactions are requested (sandbox may return none)
4) A console dashboard prints summaries and per-account details
5) Raw portfolio responses are saved under `artifacts/portfolio/` with timestamped filenames

## Project structure

```
.
├── main.py
├── requirements.txt
├── .env.example
├── Securities_sandbox.json
├── certs/
│   ├── dev-localhost.crt
│   └── dev-localhost.key
├── config/
│   ├── __init__.py
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── callback_server.py
│   │   └── oauth_manager.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── bank_connector.py
│   ├── aggregator/
│   │   ├── __init__.py
│   │   └── data_aggregator.py
│   └── dashboard/
│       ├── __init__.py
│       └── console_display.py
└── artifacts/
    └── portfolio/
```

## TLS certificates (local dev)

The local HTTPS callback requires TLS cert/key files. Self-signed development certs are included under `certs/`. If you prefer to generate your own:

```bash
# optional regeneration (example):
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/dev-localhost.key -out certs/dev-localhost.crt -days 365 -subj "/CN=localhost"
```

Make sure `TLS_CERT_PATH` and `TLS_KEY_PATH` in `.env` point to these files.

## Troubleshooting

- Browser/callback doesn’t open: Copy the printed authorization URL and open it manually; approve and ensure the redirect hits https://localhost:8443/callback.
- 404s on callback: We serve `/`, `/favicon.ico`, and `/callback`; ensure the path is exactly `/callback`.
- invalid_scope: Set `BANK_SCOPE` appropriately or leave blank if not required by your client.
- Token encryption key errors: Provide `TOKEN_ENCRYPTION_KEY`; if not base64, a valid Fernet key will be derived automatically.
- Sandbox returns no transactions: This is expected at times; positions and total values should still display.

## Development

Formatting and linting:

```bash
black .
flake8 .
```

Type checking:

```bash
mypy .
```

Tests (if/when added):

```bash
pytest
```

## Security

- OAuth tokens are encrypted before storage in-memory using cryptography.Fernet
- Sensitive values come from environment variables; secrets aren’t logged

## Roadmap

- Web UI dashboard
- Token persistence across runs
- Config flag to toggle artifact saving
- Multi-currency normalization and analytics
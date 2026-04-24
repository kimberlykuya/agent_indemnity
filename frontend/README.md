# Agent Indemnity Frontend

This frontend is a Next.js dashboard for the Agent Indemnity backend.

It provides two main views:
- `/` shows the compliance dashboard with bond balance, transaction feed, route distribution, bond chart, and margin table
- `/demo` shows the customer chat view with wallet entry, payment challenge, paid reply, and live slash / payout alerts

## What It Consumes

The frontend reads from the backend API and WebSocket:
- `POST /agent/chat`
- `GET /transactions`
- `GET /bond/status`
- `GET /ws` via WebSocket upgrade

## Local Development

Install dependencies and start the dev server:

```bash
npm install
npm run dev
```

By default the app runs on `http://localhost:3000`.

## Frontend Environment Variables

The frontend currently uses:
- `NEXT_PUBLIC_API_URL`
  - default: `http://localhost:8000`
  - used for REST API requests
- `NEXT_PUBLIC_WS_URL`
  - default: `ws://localhost:8000/ws`
  - used for live transaction and slash events
- `NEXT_PUBLIC_ARC_EXPLORER_TX_BASE_URL`
  - default: `https://testnet.arcscan.app/tx`
  - used to build transaction explorer links in the UI

## Notes

- The frontend reflects backend truth; it does not execute contract transactions directly
- Demo chat requests are wallet-bound and use a `402` challenge / retry flow on the same `POST /agent/chat` endpoint
- Manual slash actions in the UI are now an admin/debug path and default to the latest paid beneficiary wallet unless overridden
- If the backend is not running, dashboard bootstrapping and live updates will fail

# Trading Desk

A paper-trading desk: a Python FastAPI backend (`backend/`) and a React + TypeScript frontend (`frontend/`). It shows positions with current price and unrealized P&L, recent orders, and an order form with market quotes.

Moved here from `accounting-agent-platform` PR #17 on 2026-10-20. It is a separate project from that app.

## How orders work

Orders go through `BrokerInterface`. Alpaca is the adapter that places them (paper trading by default). Short sales are part of that interface (`sell_short`, `buy_to_cover`) so a TradeZero adapter can be added later without changing the API. The TradeZero module is a stub and returns HTTP 501.

`sell_short` and `buy_to_cover` are sent to Alpaca as equity `sell` and `buy` orders. Alpaca opens a short only when that account has shorting enabled. TradeZero is the intended place for locate and native short-sale handling (`backend/app/brokers/tradezero.py`).

The order form can mark a day limit order as extended hours. `BrokerInterface` carries `extended_hours`, and the Alpaca adapter sends it as Alpaca's `extended_hours` field. Market orders cannot use it.

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env             # then fill in ALPACA_API_KEY and ALPACA_API_SECRET
uvicorn app.main:app --reload --port 8000
```

The API is at `http://127.0.0.1:8000`. Interactive docs are at `http://127.0.0.1:8000/docs`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` to the backend. To point at a different API, set `VITE_API_BASE_URL` (see `frontend/.env.example`).

## Environment variables

Copy `backend/.env.example` to `backend/.env`. Real keys stay in `.env`, which is gitignored.

| Variable | Required | Purpose |
| --- | --- | --- |
| `BROKER` | no | `alpaca` (default). `tradezero` is reserved for short selling and is not implemented. |
| `ALPACA_API_KEY` | yes, for Alpaca | Paper or live key id from the Alpaca dashboard. |
| `ALPACA_API_SECRET` | yes, for Alpaca | API secret. Never commit this. |
| `ALPACA_BASE_URL` | no | Defaults to `https://paper-api.alpaca.markets`. Live trading is `https://api.alpaca.markets`. |

Paper keys: [Alpaca paper dashboard](https://app.alpaca.markets/paper/dashboard/overview).

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

CI runs the backend tests and the frontend build on every push and pull request.

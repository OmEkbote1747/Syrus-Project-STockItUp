# Live API status

This file replaces the earlier instructions for enabling a live 021 Trade connection. Those instructions described an integration that is not wired into the running application.

## Market data

The backend can use demo quotes, Yahoo Finance, or Twelve Data. Setup instructions are in [STOCK_API_INTEGRATION.md](STOCK_API_INTEGRATION.md). External quote data does not change the broker used for portfolios or order execution.

## Brokerage execution

021 Trade credentials, positions, and order placement are not connected to the app's approval or execution routes. The local mock broker remains the only execution path. The mock API deliberately refuses to start when `USE_REAL_API=true`; do not set it expecting to enable live trading.

The `backend/services/trade021_api.py` file is an isolated client prototype, not a production-ready integration. It lacks the symbol-token mapping, normalized account/order schemas, execution reconciliation, and end-to-end verification needed to connect it safely. Never enter brokerage credentials or attempt live orders using this prototype.

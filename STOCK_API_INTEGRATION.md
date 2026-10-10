# Market data configuration

Market data and order execution are separate integrations. The default is `demo`: the app reads fixed quotes from the local mock broker and clearly labels them as demo data. Set `MARKET_DATA_PROVIDER=yahoo` to use Yahoo Finance, or `MARKET_DATA_PROVIDER=twelve_data` with a Twelve Data key to use that API for quotes and historical price series. The chosen provider is used by Market Watch, the ticker, chat quotes, and the quote displayed on order drafts. Portfolio and order execution remain on the mock broker.

## Configure a market data provider

In PowerShell, from the project directory:

```dotenv
# .env.local (backend container only)
MARKET_DATA_PROVIDER=twelve_data
TWELVE_DATA_API_KEY=your-provider-key
```

For Yahoo Finance, set `MARKET_DATA_PROVIDER=yahoo`; it does not require an API key. For the demo feed, use `MARKET_DATA_PROVIDER=demo`. After changing `.env.local`, recreate the backend so Compose passes the updated settings:

```powershell
docker compose up -d --force-recreate backend
```

Never put provider credentials in frontend environment variables. The Twelve Data poller refreshes every 15 minutes to limit repeated API calls; manual chart history requests also consume provider quota. Use a plan with suitable exchange coverage and request limits.

## API surface

- `GET /chat/price-snapshot` returns the latest available quotes with `provider`, `mode`, and `updated_at` metadata.
- `GET /market/history/{symbol}?days=30` returns historical close points for the selected market chart. `days` accepts 1–365.
- Yahoo Finance and Twelve Data quotes can be delayed, limited by plan, or temporarily unavailable. External mode does not fill missing values with demo prices; inspect the feed status and try again later.
- Demo history is built only from quote snapshots observed while the app is running. It is not backfilled or presented as historical market data.

## Provider and trading safety

The Yahoo adapter in `backend/services/stock_data_service.py` uses `yfinance` and does not require a key. The Twelve Data adapter uses the provider's `/quote`, `/time_series`, and `/symbol_search` endpoints and maps the app's `.NS`/`.BO` symbols to exchange-qualified symbols. See [Twelve Data quote and time-series docs](https://twelvedata.com/docs) for plan availability and API response details.

The mock broker continues to own portfolio, order preparation, approval, and execution status. A quote-provider change never enables live brokerage execution. The dashboard must continue to label mock-broker orders as demo/simulated; only a separately integrated broker can report real execution.

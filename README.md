# CryptoEsim engine

Algorand USDC checkout and eSIM Access fulfilment. The server persists the order, confirmed payment, encrypted delivery and signed receipt. It returns x402 `PAYMENT-REQUIRED` and `PAYMENT-RESPONSE` headers. The buyer signs in their wallet; the server never requests a wallet seed.

## Render

- Type: Web Service, Python. Name: `cryptoesim-api`.
- Build: `pip install -r esim-runtime.txt`
- Start: `uvicorn esim_switchboard:app --host 0.0.0.0 --port $PORT`
- Health: `/health`. One instance, one worker. Managed PostgreSQL in the same region.

Required configuration: `DATABASE_URL`, `PAYTO_ADDRESS`, `ESIM_ACCESS_CODE`, `CRYPTOESIM_SECRET` (random 32-byte secret encoded as URL-safe Base64), `STORE_ORIGIN` (exact HTTPS storefront origin), `SUPPORT_EMAIL`, `TAX_BPS` (tax rate in basis points; select the applicable rate). Set `LIVE_SALES_ENABLED=false` while setting up, then explicitly set `true` to accept purchases. `MERCHANT_NAME` defaults to CryptoEsim; set it to your seller identity if different.

On Render, the default mode is Mainnet and the API origin comes from `RENDER_EXTERNAL_URL`. Locally, the default mode is a simulated preview. Mainnet requires the provider credentials and persistent PostgreSQL; configuration cannot silently fall back to simulated fulfilment.

The master secret deterministically derives separate receipt-signing, delivery-encryption and operator-access keys. Keep a secure backup and do not rotate it without a migration plan: existing deliveries depend on it. Never put secrets or recovery files in Git.

The provider account needs a prepaid balance separate from USDC received on Algorand. Mainnet payment does not automatically fund the provider. Default destinations: ES, JP, MA, US, GB, TR; `ALLOWED_COUNTRIES` can select other supported ISO country codes. Plans are fetched from the provider, not pre-purchased inventory.

API: `GET /api/config`, `GET /api/plans?country=ES`, `POST /api/orders`, `POST /api/pay`, `GET /api/orders/{id}`, `POST /api/orders/{id}/resume`. Order access requires its bearer recovery token. Unknown settlement and supplier outcomes remain pending or require operator review instead of triggering a blind second purchase. Refunds require operator handling and a verified refund transaction; they are not automatically sent by this server.

Browser files are in the separate `cryptoesim-storefront` repository. This backend starts independently without them. CORS only permits the configured storefront origin and exposes the x402 receipt headers.

Validation performed: simulated purchases, top-ups, receipt verification, persistence and cross-origin browser integration. No funded Lute signature, real supplier issuance or live Render deployment has been performed for this release. No tests or development dependencies are included.

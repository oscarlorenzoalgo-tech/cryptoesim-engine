# CryptoEsim — Backend

**Buy travel eSIMs with USDC on Algorand through an x402-powered checkout.**

CryptoEsim connects a crypto payment to a useful service: mobile data. Travelers use the web storefront, while developers and authorized agents can use the same paid API to purchase a data plan or a compatible top-up.

- [Storefront](https://cryptoesim-eqyv.onrender.com/)
- [API integration guide and payment client](https://cryptoesim-eqyv.onrender.com/#api)
- [Public API configuration](https://cryptoesim-engine.onrender.com/api/config)
- [Discovery manifest](https://cryptoesim-engine.onrender.com/.well-known/x402.json)
- [GoPlausible merchant page](https://facilitator.goplausible.xyz/dashboard/merchants/c44019bc97d89323)

## What this repository does

The FastAPI service retrieves plans from eSIM Access, calculates an order-specific USDC price, verifies and settles the customer's x402 payment through GoPlausible, and requests the purchased eSIM from the supplier. PostgreSQL preserves the order, transaction, delivery state and audit events across deployments.

The customer signs the payment locally. The backend does not request the customer's wallet seed. Activation details are encrypted in the database, and completed orders include an Ed25519-signed receipt binding the request, plan, price, delivery and payment.

## Purchase flow

1. Read available destinations and plans. Availability comes from the configured supplier catalog.
2. Create an order after confirming device compatibility and accepting the terms. The server checks supplier balance and locks a quote.
3. Read the HTTP `402 Payment Required` response and its `PAYMENT-REQUIRED` header.
4. Sign the exact Algorand USDC transfer and send the x402 payload in `PAYMENT-SIGNATURE` to `POST /api/pay`.
5. The backend verifies the payload, calls GoPlausible `/verify` and `/settle`, and confirms the transaction on Algorand.
6. The backend requests fulfilment from eSIM Access. The storefront moves the buyer to **My eSIMs** when payment is confirmed and displays installation details when delivery is ready and its receipt has been verified.

Payment confirmation and eSIM issuance are separate states. Supplier processing can be asynchronous. Recover a paid order using its existing ID and recovery token instead of creating another purchase.

## Repository files

| File | Purpose |
| --- | --- |
| `esim_switchboard.py` | API, configuration, pricing, payments, supplier integration, persistence and recovery |
| `esim-runtime.txt` | Pinned Python dependencies |
| `.python-version` | Python version for Render |
| `.gitignore` | Excludes local environments, credentials and runtime data |
| `README.md` | This guide |

The storefront belongs in the separate `cryptoesim-storefront` repository. This backend runs independently without frontend files.

## Deploy on Render

Create a Python **Web Service** connected to this repository. Keep the files at the repository root.

| Setting | Value |
| --- | --- |
| Service name | `cryptoesim-engine` |
| Branch | `main` |
| Root directory | Leave empty |
| Build command | `pip install -r esim-runtime.txt` |
| Start command | `uvicorn esim_switchboard:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |

Use persistent PostgreSQL in the same region. Run one service instance with one Uvicorn worker for the included recovery worker. A local database file is not used for live payments.

### Minimum environment configuration

| Variable | Value or purpose |
| --- | --- |
| `DATABASE_URL` | Persistent PostgreSQL connection URL; use Render's internal URL when available |
| `PAYTO_ADDRESS` | Your Algorand receiving address, opted in to Mainnet USDC |
| `ESIM_ACCESS_CODE` | Private eSIM Access API credential |
| `CRYPTOESIM_SECRET` | A strong, random server secret of at least 43 characters |
| `STORE_ORIGIN` | Exact storefront origin, currently `https://cryptoesim-eqyv.onrender.com`, without a trailing slash |
| `SUPPORT_EMAIL` | Customer support address |
| `TAX_BPS` | Explicit tax configuration in basis points; set the rate applicable to your business |
| `LIVE_SALES_ENABLED` | `false` during setup; `true` when the service is ready to accept purchases |

Generate the server secret locally, store it securely, and enter it only in the backend environment:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Keep this value stable across deployments. It derives the receipt-signing, delivery-encryption and operator-access keys. Back up the secret and database together; replacing the secret without a migration prevents access to existing encrypted deliveries.

On Render, the default mode is Mainnet and the public origin comes from `RENDER_EXTERNAL_URL`. There is no need to add `APP_MODE` or `PUBLIC_BASE_URL` for this standard setup. `MERCHANT_NAME` defaults to `CryptoEsim`. The optional `ALLOWED_COUNTRIES` setting selects supported ISO country codes, separated by commas. Countries are not hardcoded in the frontend.

Commit updates and deploy the latest commit. Preserve the existing database, receiving address and server secret.

## eSIM Access and pricing

The customer pays USDC to the merchant's Algorand address. eSIM Access separately charges the merchant's prepaid supplier balance. The integration does not convert USDC or automatically fund the supplier account.

Plans are ordered on demand using the supplier's catalog `packageCode`; the merchant does not have to buy inventory for every country in advance. The backend checks supplier balance before quoting and again before submitting payment. Base orders use a stable supplier transaction ID so recovery does not intentionally create a second purchase. Ambiguous top-up outcomes require operator review.

Prices depend on the selected package and the configured pricing policy. Never hardcode a previous quote in a client: validate the current amount, network, asset and receiving address before signing.

## API reference

| Method and path | Purpose | Access |
| --- | --- | --- |
| `GET /health` | Service and database health | Public |
| `GET /api/config` | Network, destinations, merchant and receipt public key | Public |
| `GET /api/plans?country=ES` | Plans and prices for one destination | Public |
| `GET /.well-known/x402.json` | Merchant identity and API discovery flow | Public |
| `GET /.well-known/cryptoesim-key.json` | Ed25519 receipt verification key | Public |
| `POST /api/orders` | Create an order and its quote | Establishes a private recovery token |
| `POST /api/pay` | Retrieve the order's 402 challenge or submit a signed payment | Order token |
| `GET /api/orders/{id}` | Read the same order and completed delivery | Order token |
| `POST /api/orders/{id}/resume` | Recover an interrupted order | Order token |
| `POST /api/orders/{id}/delivery` | Refresh an already-created supplier order | Order token |
| `GET /api/orders/{id}/events` | Read the order's audit events | Order token |
| `GET /api/orders/{id}/qr` | Private installation QR for a completed eSIM | Order token |
| `GET /api/orders/{id}/usage` | Supplier-reported consumption | Order token |
| `GET /api/orders/{id}/topup-plans` | Compatible top-up plans | Order token |

For order access, send `Authorization: Bearer <recovery-token>`. Persist the order ID and token before continuing. Clients can supply `Idempotency-Key` and `X-Recovery-Token` when creating the order. Top-ups also require authorization for the original eSIM through `X-Parent-Token`.

`POST /api/pay` uses a JSON body containing `order_id`. Without a payment signature, a valid quoted order returns `402`. A pending payment or delivery returns `202`; a completed order returns `200`. An expired unpaid quote returns `410`. `PAYMENT-RESPONSE` is returned when a payment has been confirmed. The signed delivery receipt is a separate field in the completed order.

Read-only examples:

```bash
curl --fail-with-body 'https://cryptoesim-engine.onrender.com/api/config'
curl --fail-with-body 'https://cryptoesim-engine.onrender.com/api/plans?country=ES'
curl --fail-with-body 'https://cryptoesim-engine.onrender.com/.well-known/x402.json'
```

For a complete purchase client, use **API → Download payment client** in the storefront. `esim-agent.mjs` requires Node.js 22+ and `algosdk@3.7.0`, installed in the buyer's private client folder. These are not backend dependencies. The client supports catalog browsing, a spending limit, local signing, receipt verification and recovery of the same order.

## Algorand, Bazaar and challenge attribution

Production payments use **USDC on Algorand Mainnet, ASA `31566704`**. USDC on another network cannot pay this API. The buyer also needs sufficient ALGO for account requirements and transaction fees.

The stable paid resource is `POST https://cryptoesim-engine.onrender.com/api/pay`. Mainnet payment requirements include `extra.tag = "x402-global-challenge"`. The backend attaches the Bazaar extension and `x402-merchant` identity before forwarding payment payloads, including for older clients that omit metadata.

The backend root publishes HTML/Open Graph branding. The discovery manifest describes the API without creating an order or advertising a fictitious fixed price. `/api/config` reports `discovery_revision: 20260929-bazaar11`.

Discovery and challenge attribution are separate from settlement. GoPlausible processes discovery metadata when payments settle; a local validation or published manifest alone does not prove a live Bazaar listing. Merchant display names may refresh independently of the stable merchant ID. There is no separate customer transfer to a competition wallet in this checkout.

## Recovery and private data

Keep recovery files, activation codes, QR images and completed receipt downloads private: they can contain access to the purchased service. Do not commit them, the supplier credential, `.env`, wallet seeds or runtime data to GitHub.

The background worker runs recovery every 15 seconds while the process is running. The browser also polls pending orders. Supplier errors and order references appear in authenticated delivery details. A confirmed payment does not guarantee that the supplier has already issued the eSIM. Refunds require operator handling and a verified refund transaction; the backend does not automatically send refunds.

## Local preview

The combined local package contains both repositories and `abrir-cryptoesim.sh`. From its `cryptoesim-local` directory, run:

```bash
bash abrir-cryptoesim.sh
```

Open `http://127.0.0.1:8093`. Use `bash abrir-cryptoesim.sh 8094` if that port is occupied. This local mode simulates payments and eSIM delivery and does not buy connectivity. Do not put production supplier credentials in a preview environment. The runtime lock targets Python 3.12.

## Implementation status and references

The public API reported Mainnet mode, enabled sales and discovery revision `20260929-bazaar11` on 29 September 2026. Local checks covered payment metadata, simulated purchases, receipt integrity, private order access and recovery. A live health check does not verify supplier issuance or activation on a physical phone.

- [Render: FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [eSIM Access API](https://docs.esimaccess.com/)
- [Algorand: discovery and leaderboard troubleshooting](https://algorand.co/blog/is-your-x402-endpoint-showing-up-in-the-facilitator-leaderboard-how-to-troubleshoot-if-not)

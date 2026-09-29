
# ---- CONFIG ----
"""Local demo is the default. A testnet payment can never purchase a real eSIM."""
import base64
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

NETWORKS = {"demo": "demo:local", "testnet": "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDe",
            "mainnet": "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73k"}
GENESIS = {"testnet": "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=",
           "mainnet": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="}
ORIGINAL_PAYTO = "SGLTUPAC7TKGKNNXKNPQ2QZCC7NJSLAKYZ7O7NOGGAPXWBFZTOLTPMSPPI"


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    database_url: str = "sqlite:///data/cryptoesim-demo.sqlite3"
    public_url: str = "http://127.0.0.1:8093"
    store_origin: str = ""
    pay_to: str = ORIGINAL_PAYTO
    facilitator_url: str = "https://facilitator.goplausible.xyz"
    algod_url: str = ""
    indexer_url: str = ""
    algod_token: str = ""
    signing_key: str = ""
    signing_key_file: str = "data/demo-signing-key.b64"
    encryption_key: str = ""
    encryption_key_file: str = "data/demo-encryption-key.b64"
    admin_token: str = ""
    esim_access_code: str = ""
    sales_enabled: bool = False
    tax_bps: int = 0
    tax_configured: bool = False
    tax_label: str = "Impuesto configurado por el vendedor"
    merchant_name: str = "CryptoEsim"
    support_email: str = ""
    allowed_countries: tuple = ("ES", "JP", "MA", "US", "GB", "TR")
    provider_timeout: int = 25
    request_timeout: float = 12.0
    quote_ttl: int = 300
    min_profit_atomic: int = 300000
    target_markup_bps: int = 1500
    overhead_atomic: int = 100000
    cost_reserve_bps: int = 300
    discount_bps: int = 1000
    usd_per_usdc: str = "1.00"
    references_file: str = "config/competitors.json"
    benchmark_max_age_hours: int = 72
    require_competitive: bool = False
    worker_enabled: bool = True

    @property
    def network(self): return NETWORKS[self.mode]
    @property
    def asset(self): return "31566704" if self.mode == "mainnet" else "10458941"
    @property
    def node_url(self): return self.algod_url or f"https://{self.mode}-api.algonode.cloud"
    @property
    def history_url(self): return self.indexer_url or f"https://{self.mode}-idx.algonode.cloud"
    @property
    def simulation(self): return self.mode != "mainnet"

    def validate(self):
        from decimal import Decimal
        if self.mode not in NETWORKS: raise ValueError("APP_MODE: demo, testnet o mainnet")
        u = urlparse(self.public_url)
        if u.scheme not in ("http", "https") or not u.hostname or u.path not in ("", "/") or u.query or u.fragment or u.username:
            raise ValueError("PUBLIC_BASE_URL debe ser un origen sin ruta")
        if self.store_origin:
            origin = urlparse(self.store_origin)
            if origin.scheme not in ("http", "https") or not origin.hostname or origin.path not in ("", "/") or origin.query or origin.fragment or origin.username:
                raise ValueError("STORE_ORIGIN must be an origin URL without a path")
            if self.mode == "mainnet" and origin.scheme != "https": raise ValueError("STORE_ORIGIN requires HTTPS on Mainnet")
        for n in (self.min_profit_atomic, self.overhead_atomic):
            if n < 0: raise ValueError("Los costes y el margen no pueden ser negativos")
        if not 0 <= self.tax_bps <= 10000 or not 0 <= self.discount_bps < 10000 or not 0 <= self.cost_reserve_bps <= 10000 or not 0 <= self.target_markup_bps <= 100000:
            raise ValueError("Porcentajes de precios fuera de rango")
        rate = Decimal(self.usd_per_usdc)
        if not rate.is_finite() or not Decimal('0.5') <= rate <= Decimal('1.5'): raise ValueError("USD_PER_USDC inválido")
        if not self.allowed_countries or any(len(x) != 2 or not x.isalpha() or not x.isupper() for x in self.allowed_countries):
            raise ValueError("ALLOWED_COUNTRIES debe contener códigos ISO de dos letras")
        if self.mode != "demo":
            from algosdk.encoding import is_valid_address
            if not is_valid_address(self.pay_to): raise ValueError("PAYTO_ADDRESS inválida")
            if u.scheme != "https" and u.hostname not in ("localhost", "127.0.0.1"): raise ValueError("Se necesita HTTPS")
            if not self.database_url.startswith(("postgres://", "postgresql")): raise ValueError("Los pagos en cadena necesitan PostgreSQL persistente")
            if len(base64.b64decode(self.signing_key, validate=True)) != 32: raise ValueError("Falta SIGNING_KEY_BASE64 de 32 bytes")
            if len(base64.urlsafe_b64decode(self.encryption_key)) != 32: raise ValueError("Falta DATA_ENCRYPTION_KEY (Fernet)")
            if len(self.admin_token) < 32: raise ValueError("ADMIN_TOKEN debe tener al menos 32 caracteres")
        if self.mode == "mainnet":
            if not self.esim_access_code: raise ValueError("Falta ESIM_ACCESS_CODE")
            if not self.tax_configured: raise ValueError("Configura TAX_BPS explícitamente antes de vender")
            if not self.support_email or "@" not in self.support_email or self.merchant_name.endswith("Demo"):
                raise ValueError("Configura MERCHANT_NAME y SUPPORT_EMAIL")
        if self.mode != "mainnet" and self.esim_access_code:
            raise ValueError("No introduzcas la clave del proveedor en demo/testnet: esas modalidades simulan las eSIM")
        if self.database_url.startswith("sqlite:///") and not self.database_url.endswith(":memory:"):
            Path(self.database_url[10:]).parent.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def from_env(cls, env_file=None):
        from dotenv import load_dotenv
        # An explicit file is useful on Linux; Render provides process variables.
        # Never expand ${...} in passwords or overwrite the hosting environment.
        selected = env_file or os.getenv("CRYPTOESIM_ENV_FILE")
        if selected and not Path(selected).is_file():
            raise ValueError("No existe el archivo de configuración indicado")
        load_dotenv(dotenv_path=selected or Path(__file__).resolve().parent / ".env", override=False, interpolate=False)
        default_mode = "mainnet" if os.getenv("RENDER") == "true" else "demo"
        if os.getenv("APP_MODE", default_mode) != "demo" and not os.getenv("PAYTO_ADDRESS"):
            raise ValueError("Configura tu propia PAYTO_ADDRESS; no se utiliza una wallet predeterminada en cadena")
        if os.getenv("APP_MODE", default_mode) != "demo" and not (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")):
            raise ValueError("Configura PUBLIC_BASE_URL; en Render puede utilizarse RENDER_EXTERNAL_URL")
        strings = {"store_origin": "STORE_ORIGIN", "mode": "APP_MODE", "database_url": "DATABASE_URL", "public_url": "PUBLIC_BASE_URL",
                   "pay_to": "PAYTO_ADDRESS", "facilitator_url": "FACILITATOR_URL", "algod_url": "ALGOD_URL",
                   "indexer_url": "INDEXER_URL", "algod_token": "ALGOD_TOKEN", "signing_key": "SIGNING_KEY_BASE64",
                   "encryption_key": "DATA_ENCRYPTION_KEY", "admin_token": "ADMIN_TOKEN", "esim_access_code": "ESIM_ACCESS_CODE",
                   "merchant_name": "MERCHANT_NAME", "support_email": "SUPPORT_EMAIL", "tax_label": "TAX_LABEL",
                   "usd_per_usdc": "USD_PER_USDC", "references_file": "COMPETITORS_FILE"}
        ints = {"tax_bps": "TAX_BPS", "min_profit_atomic": "MIN_PROFIT_ATOMIC", "target_markup_bps": "TARGET_MARKUP_BPS",
                "overhead_atomic": "OVERHEAD_ATOMIC", "cost_reserve_bps": "COST_RESERVE_BPS", "discount_bps": "DISCOUNT_BPS"}
        args = {key: os.environ[env] for key, env in strings.items() if env in os.environ}
        args.setdefault("mode", default_mode)
        for key, env in ints.items():
            if env in os.environ:
                try: args[key] = int(os.environ[env])
                except ValueError: raise ValueError(f"{env} debe ser un número entero") from None
        for env in ("LIVE_SALES_ENABLED", "REQUIRE_COMPETITIVE", "WORKER_ENABLED"):
            if env in os.environ and os.environ[env] not in ("true", "false"):
                raise ValueError(f"{env}: escribe true o false")
        args.update(sales_enabled=os.getenv("LIVE_SALES_ENABLED") == "true", tax_configured="TAX_BPS" in os.environ,
                    require_competitive=os.getenv("REQUIRE_COMPETITIVE") == "true", worker_enabled=os.getenv("WORKER_ENABLED", "true") == "true")
        if os.getenv("ALLOWED_COUNTRIES"): args["allowed_countries"] = tuple(x.strip().upper() for x in os.environ["ALLOWED_COUNTRIES"].split(","))
        args["public_url"] = (args.get("public_url") or os.getenv("RENDER_EXTERNAL_URL") or cls.public_url).rstrip("/")
        secret = os.getenv("CRYPTOESIM_SECRET", "")
        if secret:
            if len(secret) < 43: raise ValueError("CRYPTOESIM_SECRET must be a random secret with at least 43 characters")
            import hashlib, hmac
            def derived(label): return hmac.new(secret.encode(), ("cryptoesim/"+label).encode(), hashlib.sha256).digest()
            args.setdefault("signing_key", base64.b64encode(derived("receipt-signing-v1")).decode())
            args.setdefault("encryption_key", base64.urlsafe_b64encode(derived("delivery-encryption-v1")).decode())
            args.setdefault("admin_token", derived("operator-access-v1").hex())
        if os.getenv("RENDER") == "true" and not args.get("store_origin"):
            raise ValueError("Set STORE_ORIGIN to the exact HTTPS storefront URL")
        return cls(**args).validate()

# ---- EVIDENCE ----
"""Canonical UTF-8 JSON, Ed25519 receipts and domain-separated Merkle proofs.

Financial measurements are decimal strings. Canonical strings are exported so
verifiers never have to guess a different language's float serialization.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def b64(value):
    return base64.b64encode(value).decode("ascii")


def encode_header(value):
    return b64(canonical(value).encode())


def decode_header(value):
    if len(value) > 24_000:
        raise ValueError("Payment header too large")
    # Accept both standard and URL-safe Base64; emit standard Base64 in responses.
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    obj = json.loads(decoded)
    if not isinstance(obj, dict):
        raise ValueError("Payment must be a JSON object")
    return obj


def leaf_hash(canonical_payload):
    return hashlib.sha256(b"\x00" + canonical_payload.encode("utf-8")).hexdigest()


def merkle_tree(leaves):
    if not leaves:
        raise ValueError("Empty receipt batch")
    levels = [[bytes.fromhex(x) for x in leaves]]
    while len(levels[-1]) > 1:
        row = levels[-1]
        levels.append([hashlib.sha256(b"\x01" + row[i] + row[min(i + 1, len(row) - 1)]).digest()
                       for i in range(0, len(row), 2)])
    paths = []
    for index in range(len(leaves)):
        path, pos = [], index
        for row in levels[:-1]:
            sibling = pos ^ 1
            path.append({"side": "left" if pos % 2 else "right",
                         "hash": row[min(sibling, len(row) - 1)].hex()})
            pos //= 2
        paths.append(path)
    return levels[-1][0].hex(), paths


def verify_merkle(leaf, path, root):
    value = bytes.fromhex(leaf)
    for item in path:
        sibling = bytes.fromhex(item["hash"])
        if item["side"] == "left":
            value = hashlib.sha256(b"\x01" + sibling + value).digest()
        elif item["side"] == "right":
            value = hashlib.sha256(b"\x01" + value + sibling).digest()
        else:
            return False
    return value.hex() == root


class ReceiptSigner:
    def __init__(self, settings):
        if settings.signing_key:
            raw = base64.b64decode(settings.signing_key, validate=True)
        else:
            path = Path(settings.signing_key_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                try:
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "w") as file:
                        file.write(b64(os.urandom(32)))
                except FileExistsError:
                    pass
            raw = base64.b64decode(path.read_text().strip(), validate=True)
        self.key = Ed25519PrivateKey.from_private_bytes(raw)
        self.public_bytes = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.key_id = hashlib.sha256(self.public_bytes).hexdigest()

    def public_document(self):
        return {"algorithm": "Ed25519", "key_id": self.key_id, "public_key_base64": b64(self.public_bytes)}

    def sign(self, payload):
        value = canonical(payload)
        return {"payload": payload, "canonical_payload": value, "signature_base64": b64(self.key.sign(value.encode())),
                "key_id": self.key_id, "commitment_sha256": leaf_hash(value)}


def verify_result(bundle, trusted_public_key):
    receipt = bundle["receipt"]
    raw_key = base64.b64decode(trusted_public_key, validate=True)
    if receipt["key_id"] != hashlib.sha256(raw_key).hexdigest(): raise ValueError("Untrusted key")
    payload = receipt["payload"]
    if canonical(payload) != receipt["canonical_payload"]: raise ValueError("Canonical payload mismatch")
    Ed25519PublicKey.from_public_bytes(raw_key).verify(base64.b64decode(receipt["signature_base64"]), receipt["canonical_payload"].encode())
    for key in ("request", "plan", "pricing", "delivery", "payment"):
        if digest(bundle[key]) != payload[key + "_sha256"]: raise ValueError("Modified " + key)
    if payload["order_id"] != bundle["order_id"] or payload["simulation"] != bundle["simulation"]: raise ValueError("Identity mismatch")
    if payload["transaction_id"] != bundle["payment"]["transaction"]: raise ValueError("Transaction mismatch")
    if leaf_hash(receipt["canonical_payload"]) != receipt["commitment_sha256"]: raise ValueError("Commitment mismatch")
    return True

# ---- STORE ----
import json
import os
import time
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import BigInteger, Column, MetaData, String, Table, Text, create_engine, event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

meta = MetaData()
orders = Table("cryptoesim_orders_v1", meta,
    Column("id", String(36), primary_key=True), Column("token_hash", String(64), nullable=False),
    Column("request_hash", String(64), nullable=False), Column("request_json", Text, nullable=False),
    Column("quote_json", Text, nullable=False), Column("status", String(32), nullable=False),
    Column("mode", String(12), nullable=False), Column("created_ms", BigInteger, nullable=False),
    Column("updated_ms", BigInteger, nullable=False), Column("expires_ms", BigInteger, nullable=False),
    Column("claim", String(36)), Column("payment_id", String(64), unique=True), Column("payer", String(64)),
    Column("payment_payload", Text), Column("payment_json", Text), Column("confirmed_round", BigInteger),
    Column("provider_transaction", String(50), unique=True), Column("provider_order", String(80)),
    Column("delivery", Text), Column("result", Text), Column("error_code", String(100)),
    Column("refund_tx", String(64), unique=True), Column("parent_id", String(36)))
events = Table("cryptoesim_events_v1", meta,
    Column("id", String(36), primary_key=True), Column("order_id", String(36), nullable=False),
    Column("at_ms", BigInteger, nullable=False), Column("event", String(80), nullable=False))
demo_profiles = Table("cryptoesim_demo_profiles_v1", meta,
    Column("id", String(60), primary_key=True), Column("data_json", Text, nullable=False))


def now_ms(): return int(time.time() * 1000)


class Vault:
    def __init__(self, cfg):
        key = cfg.encryption_key
        if not key:
            p = Path(cfg.encryption_key_file); p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                try:
                    with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f: f.write(Fernet.generate_key())
                except FileExistsError: pass
            key = p.read_bytes().strip()
        self.fernet = Fernet(key)
    def seal(self, value): return self.fernet.encrypt(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).decode()
    def open(self, value): return json.loads(self.fernet.decrypt(value.encode())) if value else None


class Store:
    def __init__(self, url):
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix): url = "postgresql+psycopg://" + url[len(prefix):]
        opts = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            opts["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in url: opts["poolclass"] = StaticPool
        self.engine = create_engine(url, **opts)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def setup(db, _): db.execute("PRAGMA journal_mode=WAL")
        meta.create_all(self.engine)
    def get(self, oid):
        with self.engine.connect() as c:
            r = c.execute(select(orders).where(orders.c.id == oid)).mappings().first()
            return dict(r) if r else None
    def insert(self, row):
        try:
            with self.engine.begin() as c: c.execute(orders.insert().values(**row))
            return True
        except IntegrityError: return False
    def change(self, oid, statuses, values, claim=None):
        cond = (orders.c.id == oid) & orders.c.status.in_(statuses)
        if claim is not None: cond &= orders.c.claim == claim
        values = {**values, "updated_ms": now_ms()}
        try:
            with self.engine.begin() as c: return c.execute(update(orders).where(cond).values(**values)).rowcount == 1
        except IntegrityError: return False
    def list(self, statuses=None, limit=100):
        query = select(orders).order_by(orders.c.updated_ms).limit(limit)
        if statuses: query = query.where(orders.c.status.in_(statuses))
        with self.engine.connect() as c: return [dict(r) for r in c.execute(query).mappings()]
    def audit(self, oid, name):
        import uuid
        with self.engine.begin() as c: c.execute(events.insert().values(id=str(uuid.uuid4()), order_id=oid, at_ms=now_ms(), event=name))
    def history(self, oid):
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(select(events.c.at_ms, events.c.event).where(events.c.order_id == oid).order_by(events.c.at_ms)).mappings()]
    def demo_get(self, key):
        with self.engine.connect() as c: value = c.execute(select(demo_profiles.c.data_json).where(demo_profiles.c.id == key)).scalar()
        return json.loads(value) if value else None
    def demo_set(self, key, value):
        # Each provider mutation is protected by the order claim; profiles survive restarts.
        with self.engine.begin() as c:
            if c.execute(select(demo_profiles.c.id).where(demo_profiles.c.id == key)).scalar():
                c.execute(update(demo_profiles).where(demo_profiles.c.id == key).values(data_json=json.dumps(value)))
            else: c.execute(demo_profiles.insert().values(id=key, data_json=json.dumps(value)))

# ---- PRICING ----
"""Integer USDC amounts; real, dated comparisons only. No scraped or fabricated discounts."""
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path


def up(value): return int(Decimal(value).to_integral_value(rounding=ROUND_CEILING))
def display(atomic): return f"{Decimal(atomic) / 1000000:.2f}"
def cents_up(atomic): return ((atomic + 9999) // 10000) * 10000


def comparable(plan):
    return {key: plan[key] for key in ("countries", "volume_bytes", "duration_days", "data_type", "speed", "activation", "networks", "fup_policy", "ip_export")}


class Pricing:
    def __init__(self, cfg): self.cfg = cfg
    def reference(self, plan):
        p = Path(self.cfg.references_file)
        if not p.exists(): return None
        values = json.loads(p.read_text())
        matches = []
        for r in values:
            try:
                checked = datetime.fromisoformat(r["checked_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - checked).total_seconds()
                if not 0 <= age <= self.cfg.benchmark_max_age_hours * 3600: continue
                if r["plan_id"] != plan["id"] or r["currency"] != "USD" or r.get("equivalence_reviewed") is not True: continue
                if r.get("features_sha256") != digest(comparable(plan)) or r.get("tax_included") is not True: continue
                if not r["source_url"].startswith("https://") or r.get("coupon_required", False): continue
                price = Decimal(r["total_price"])
                if not price.is_finite() or price <= 0: continue
                matches.append((price, r))
            except (KeyError, TypeError, ValueError, ArithmeticError): continue
        return min(matches, key=lambda x: x[0])[1] if matches else None
    def calculate(self, plan):
        cfg = self.cfg
        fx = Decimal(cfg.usd_per_usdc)
        cost = up(Decimal(plan["cost_units"]) * 100 / fx)  # provider 1 USD = 10,000; USDC = 1,000,000
        expenses = cost + cfg.overhead_atomic + up(Decimal(cost) * cfg.cost_reserve_bps / 10000)
        floor_net = expenses + cfg.min_profit_atomic
        tax_factor = Decimal(1) + Decimal(cfg.tax_bps) / 10000
        floor = cents_up(up(Decimal(floor_net) * tax_factor))
        normal_net = max(floor_net, expenses + up(Decimal(cost) * cfg.target_markup_bps / 10000))
        price = cents_up(up(Decimal(normal_net) * tax_factor))
        ref = self.reference(plan)
        competitive = None
        benchmark = None
        if ref:
            reference_atomic = int((Decimal(ref["total_price"]) / fx * 1000000).to_integral_value(rounding=ROUND_FLOOR))
            target = int(Decimal(reference_atomic) * (10000 - cfg.discount_bps) / 10000) // 10000 * 10000
            price = max(floor, min(price, target))
            competitive = price <= target and price < reference_atomic
            benchmark = {"seller": ref["seller"], "price_usd": ref["total_price"], "source_url": ref["source_url"], "checked_at": ref["checked_at"],
                         "discount_bps": int(10000 * (reference_atomic - price) / reference_atomic) if price < reference_atomic else 0}
        if cfg.require_competitive and competitive is not True: return None
        net = int(Decimal(price) / tax_factor)
        return {"amount_atomic": str(price), "total_usdc": display(price), "tax_atomic": str(price - net),
                "tax_bps": cfg.tax_bps, "tax_label": cfg.tax_label, "competitive": competitive, "benchmark": benchmark,
                "pricing_version": "cryptoesim-pricing-v1", "usd_per_usdc": cfg.usd_per_usdc,
                "internal": {"supplier_cost_atomic": cost, "expenses_atomic": expenses, "net_margin_atomic": net - expenses,
                             "minimum_total_atomic": floor}}

# ---- PROVIDER ----
"""eSIM Access V1 adapter. Source: published Postman collection 2s93mBxf3q.

Only fixed-data plans (dataType 1, DAY) are offered. Day passes/FUP need different
ordering and economics. AccessCode never reaches a browser. No paid API retries
are hidden inside this adapter.
"""
import copy
import hashlib
import threading
import time
from datetime import datetime, timezone
import httpx


class ProviderUnavailable(Exception): pass
class ProviderRejected(Exception):
    def __init__(self, code): self.code = str(code); super().__init__("provider_rejected_" + self.code)


def normalize(p):
    if p.get("currencyCode") != "USD" or p.get("dataType") != 1 or p.get("durationUnit") != "DAY": return None
    required = ("slug", "price", "volume", "duration", "location", "activeType")
    if any(p.get(k) is None for k in required): return None
    if type(p["price"]) is not int or p["price"] <= 0 or type(p["volume"]) is not int or p["volume"] <= 0: return None
    if not isinstance(p["duration"], int) or p["duration"] <= 0 or p["activeType"] not in (1, 2): return None
    return {"id": str(p["slug"]), "name": str(p.get("name", p["slug"])), "cost_units": p["price"],
            "countries": sorted(x.strip() for x in p["location"].split(",") if x.strip()), "volume_bytes": p["volume"],
            "duration_days": p["duration"], "data_type": 1, "speed": p.get("speed", "No especificada"),
            "activation": "installation" if p["activeType"] == 1 else "first_connection",
            "topup_supported": p.get("supportTopUpType") in (2, 3), "ip_export": p.get("ipExport", ""),
            "networks": p.get("locationNetworkList", []), "fup_policy": p.get("fupPolicy", ""),
            "package_code": p.get("packageCode", ""), "unused_valid_days": p.get("unusedValidTime")}


class ESIMAccess:
    BASE = "https://api.esimaccess.com/api/v1/open"
    def __init__(self, cfg):
        self.http = httpx.Client(timeout=cfg.provider_timeout, follow_redirects=False,
            headers={"RT-AccessCode": cfg.esim_access_code, "Content-Type": "application/json"})
        self.lock = threading.Lock(); self.last = 0.0; self.cache = {}
    def post(self, endpoint, body):
        # Single instance default, <= 5 calls/second, below the documented 8/s cap.
        with self.lock:
            delay = 0.21 - (time.monotonic() - self.last)
            if delay > 0: time.sleep(delay)
            self.last = time.monotonic()
        try:
            r = self.http.post(self.BASE + endpoint, json=body); r.raise_for_status(); value = r.json()
            if not isinstance(value, dict): raise ValueError()
            if value.get("success") is not True:
                raise ProviderRejected(value.get("errorCode", "unknown"))
            obj = value.get("obj")
            if not isinstance(obj, dict): raise ValueError()
            return obj
        except (httpx.HTTPError, ValueError, TypeError) as e: raise ProviderUnavailable("provider_unavailable") from e
    def plans(self, country, profile=None, fresh=False):
        key = (country, profile)
        if not fresh and key in self.cache and time.time() - self.cache[key][0] < 60: return copy.deepcopy(self.cache[key][1])
        body = {"type": "TOPUP" if profile else "BASE", "locationCode": country, "dataType": "1"}
        if profile: body["iccid"] = profile
        rows = self.post("/package/list", body).get("packageList")
        if not isinstance(rows, list): raise ProviderUnavailable("malformed_catalog")
        plans = [v for p in rows if isinstance(p, dict) and (v := normalize(p)) and country in v["countries"]]
        self.cache[key] = (time.time(), plans)
        return plans
    def balance(self): return int(self.post("/balance/query", {})["balance"])
    def order(self, transaction_id, plan):
        obj = self.post("/esim/order", {"transactionId": transaction_id, "amount": plan["cost_units"],
            "packageInfoList": [{"slug": plan["id"], "count": 1, "price": plan["cost_units"]}]})
        if not obj.get("orderNo"): raise ProviderUnavailable("missing_provider_order")
        if obj.get("transactionId") not in (None, transaction_id): raise ProviderUnavailable("provider_transaction_mismatch")
        return str(obj["orderNo"])
    def profile(self, order_no=None, profile_id=None):
        body = {"pager": {"pageNum": 1, "pageSize": 5}}
        if profile_id: body["esimTranNo"] = profile_id
        elif order_no: body["orderNo"] = order_no
        else: raise ValueError("profile identifier required")
        obj = self.post("/esim/query", body)
        rows = obj.get("esimList")
        if not isinstance(rows, list): raise ProviderUnavailable("malformed_profile_response")
        if not rows: return None
        if len(rows) != 1: raise ProviderUnavailable("ambiguous_profile")
        p = rows[0]
        if not isinstance(p, dict): raise ProviderUnavailable("malformed_profile_response")
        if (profile_id and p.get("esimTranNo") != profile_id) or (order_no and p.get("orderNo") != order_no):
            raise ProviderUnavailable("provider_profile_mismatch")
        return p
    def topup(self, transaction_id, plan, profile_id):
        obj = self.post("/esim/topup", {"transactionId": transaction_id, "esimTranNo": profile_id,
            "slug": plan["id"], "amount": str(plan["cost_units"])})
        if obj.get("transactionId") != transaction_id: raise ProviderUnavailable("provider_transaction_mismatch")
        return obj
    def usage(self, profile_id):
        rows = self.post("/esim/usage/query", {"esimTranNoList": [profile_id]}).get("esimUsageList", [])
        rows = [x for x in rows if x.get("esimTranNo") == profile_id]
        if len(rows) != 1: raise ProviderUnavailable("usage_unavailable")
        return {"used_bytes": int(rows[0]["dataUsage"]), "total_bytes": int(rows[0]["totalData"]),
                "provider_updated_at": rows[0]["lastUpdateTime"], "delayed_hours": "2–3", "simulation": False}


class DemoProvider:
    def __init__(self, store): self.store = store; self.order_calls = 0; self.topup_calls = 0
    def plans(self, country, profile=None, fresh=False):
        # Deliberately invented demo costs. They are never used in mainnet.
        result = []
        for gb, days, units in ((1, 7, 14000), (3, 15, 33000), (5, 30, 48000)):
            result.append({"id": f"DEMO_{country}_{gb}_{days}" + ("_TOPUP" if profile else ""),
                "name": f"{country} · {gb} GB · {days} días", "cost_units": units, "countries": [country],
                "volume_bytes": gb * 1073741824, "duration_days": days, "data_type": 1, "speed": "4G/5G simulado",
                "activation": "first_connection", "topup_supported": True, "networks": [], "fup_policy": "",
                "ip_export": "SIMULATED", "package_code": "DEMO", "unused_valid_days": 180})
        return result
    def balance(self): return 100000000
    def order(self, transaction_id, plan):
        key = "order:" + transaction_id
        old = self.store.demo_get(key)
        if old: return old["orderNo"]
        self.order_calls += 1
        suffix = hashlib.sha256(transaction_id.encode()).hexdigest()[:20]
        p = {"orderNo": "DEMO-" + suffix, "esimTranNo": "DEMO-P-" + suffix,
             "iccid": "DEMO-" + suffix, "ac": "CRYPTOESIM-DEMO-NOT-AN-ESIM:" + suffix,
             "smdpStatus": "RELEASED", "esimStatus": "GOT_RESOURCE", "apn": "demo.invalid", "totalVolume": plan["volume_bytes"],
             "orderUsage": 0, "totalDuration": plan["duration_days"], "expiredTime": None,
             "transactionId": transaction_id, "simulation": True}
        self.store.demo_set(key, p); self.store.demo_set(p["orderNo"], p); self.store.demo_set(p["esimTranNo"], p)
        return p["orderNo"]
    def profile(self, order_no=None, profile_id=None): return self.store.demo_get(profile_id or order_no)
    def topup(self, transaction_id, plan, profile_id):
        old = self.store.demo_get("topup:" + transaction_id)
        if old: return old
        self.topup_calls += 1
        p = self.profile(profile_id=profile_id)
        p["totalVolume"] += plan["volume_bytes"]; p["totalDuration"] += plan["duration_days"]
        self.store.demo_set(profile_id, p); self.store.demo_set(p["orderNo"], p)
        obj = {"transactionId": transaction_id, "topUpEsimTranNo": "DEMO-T-" + transaction_id,
               "iccid": p["iccid"], "totalVolume": p["totalVolume"], "totalDuration": p["totalDuration"], "orderUsage": p["orderUsage"]}
        self.store.demo_set("topup:" + transaction_id, obj)
        return obj
    def usage(self, profile_id):
        p = self.profile(profile_id=profile_id)
        return {"used_bytes": p["orderUsage"], "total_bytes": p["totalVolume"], "simulation": True,
                "provider_updated_at": datetime.now(timezone.utc).isoformat(), "delayed_hours": "0 (demo)"}
    def consume(self, profile_id, amount):
        p = self.profile(profile_id=profile_id)
        p["orderUsage"] = min(p["totalVolume"], p["orderUsage"] + amount)
        p["esimStatus"] = "IN_USE"
        self.store.demo_set(profile_id, p); self.store.demo_set(p["orderNo"], p)

# ---- PAYMENTS ----
from dataclasses import dataclass
import hashlib
import json
import secrets
import time

import httpx
from algosdk import encoding, transaction



class InvalidPayment(Exception):
    pass


class PaymentUnavailable(Exception):
    pass


@dataclass
class PaymentIdentity:
    transaction_id: str
    payer: str
    last_valid_round: int


def inspect_avm_payload(payload, requirement, resource_url, mode):
    """Derive the replay key from the signed transaction, never from wrapper JSON."""
    try:
        if payload.get("x402Version") != 2:
            raise InvalidPayment("unsupported_payment_version")
        accepted = payload["accepted"]
        for field in ("scheme", "network", "asset", "amount", "payTo"):
            if str(accepted.get(field)) != str(requirement[field]):
                raise InvalidPayment("payment_terms_mismatch")
        if payload.get("resource", {}).get("url") != resource_url:
            raise InvalidPayment("payment_resource_mismatch")
        group, index = payload["payload"]["paymentGroup"], payload["payload"]["paymentIndex"]
        if not isinstance(group, list) or len(group) != 1 or type(index) is not int or not 0 <= index < len(group):
            raise InvalidPayment("invalid_payment_group")
        signed = encoding.msgpack_decode(group[index])
        if not isinstance(signed, transaction.SignedTransaction) or not signed.signature:
            raise InvalidPayment("signed_asset_transfer_required")
        txn = signed.transaction
        if not isinstance(txn, transaction.AssetTransferTxn):
            raise InvalidPayment("asset_transfer_required")
        if txn.amount != int(requirement["amount"]) or txn.index != int(requirement["asset"]) or txn.receiver != requirement["payTo"]:
            raise InvalidPayment("signed_transfer_terms_mismatch")
        if txn.sender == txn.receiver:
            raise InvalidPayment("self_payment_not_allowed")
        if txn.genesis_hash != GENESIS[mode]:
            raise InvalidPayment("signed_transfer_network_mismatch")
        if txn.rekey_to or txn.close_assets_to or txn.revocation_target:
            raise InvalidPayment("unsafe_transfer_fields")
        if txn.fee > 10000:
            raise InvalidPayment("unexpected_transaction_fee")
        return PaymentIdentity(txn.get_txid(), txn.sender, txn.last_valid_round)
    except InvalidPayment:
        raise
    except Exception as exc:
        raise InvalidPayment("malformed_payment_payload") from exc


class LiveGateway:
    def __init__(self, settings):
        self.settings = settings
        self.http = httpx.Client(timeout=settings.request_timeout, follow_redirects=False)
        self._facilitator_network = None
        self._network_checked_at = 0.0

    def inspect(self, payload, requirements, url):
        return inspect_avm_payload(payload, requirements, url, self.settings.mode)

    def _post(self, endpoint, payload, requirements):
        try:
            # Current SDK uses CAIP-2 (32 chars). Some facilitators still register
            # the full genesis hash. Negotiate only these two equivalent aliases;
            # never change signed bytes, amount, asset, destination or resource.
            if self._facilitator_network is None or time.monotonic() - self._network_checked_at > 600:
                supported = self.http.get(self.settings.facilitator_url.rstrip("/") + "/supported")
                supported.raise_for_status()
                networks = {kind.get("network") for kind in supported.json().get("kinds", [])
                            if kind.get("scheme") == "exact" and kind.get("x402Version") == 2}
                aliases = (self.settings.network, "algorand:" + GENESIS[self.settings.mode])
                network = next((value for value in aliases if value in networks), None)
                if network is None: raise PaymentUnavailable("facilitator_network_not_supported")
                self._facilitator_network = network
                self._network_checked_at = time.monotonic()
            outgoing_requirements = {**requirements, "network": self._facilitator_network}
            outgoing_payload = {**payload, "accepted": {**payload["accepted"], "network": self._facilitator_network}}
            response = self.http.post(self.settings.facilitator_url + endpoint,
                                      json={"x402Version": payload.get("x402Version", 2),
                                            "paymentPayload": outgoing_payload, "paymentRequirements": outgoing_requirements},
                                      timeout=35 if endpoint == "/settle" else self.settings.request_timeout)
            response.raise_for_status()
            obj = response.json()
            if not isinstance(obj, dict):
                raise ValueError("Invalid response")
            return obj
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentUnavailable("facilitator_unavailable") from exc

    def verify(self, payload, requirements, identity):
        result = self._post("/verify", payload, requirements)
        if result.get("isValid") is not True:
            raise InvalidPayment("facilitator_rejected_payment")
        if result.get("payer") and result["payer"] != identity.payer:
            raise InvalidPayment("payer_mismatch")

    def settle(self, payload, requirements, identity):
        result = self._post("/settle", payload, requirements)
        if result.get("success") is not True:
            raise PaymentUnavailable("settlement_not_confirmed")
        if result.get("transaction") != identity.transaction_id:
            raise PaymentUnavailable("settlement_transaction_mismatch")
        network = result.get("network")
        # Older facilitator releases may emit the full genesis hash alias.
        aliases = {self.settings.network, "algorand:" + GENESIS[self.settings.mode]}
        if network not in aliases or (result.get("payer") and result["payer"] != identity.payer):
            raise PaymentUnavailable("settlement_identity_mismatch")
        return {"success": True, "transaction": identity.transaction_id,
                "network": self.settings.network, "payer": identity.payer}

    def confirmed(self, payment_id):
        """Algod plus Indexer fallback: recovery also works after the pending cache expires."""
        headers = {"X-Algo-API-Token": self.settings.algod_token} if self.settings.algod_token else {}
        try:
            response = self.http.get(self.settings.node_url + "/v2/transactions/pending/" + payment_id, headers=headers)
            if response.status_code == 200:
                info = response.json()
                if int(info.get("confirmed-round", 0)) > 0:
                    return {"round": int(info["confirmed-round"]), "source": "algod"}
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        try:
            response = self.http.get(self.settings.history_url + "/v2/transactions/" + payment_id)
            if response.status_code == 200:
                info = response.json().get("transaction", {})
                if info.get("id") == payment_id and int(info.get("confirmed-round", 0)) > 0:
                    return {"round": int(info["confirmed-round"]), "source": "indexer"}
        except (httpx.HTTPError, ValueError, TypeError):
            pass
        return None  # Unknown is NEVER interpreted as proof of non-payment.


class DemoGateway:
    """Offline simulation only; never instantiated in a live mode."""
    def __init__(self, store=None):
        self.store = store
        self.settle_calls = 0
        self.confirmations = {}

    def inspect(self, payload, requirements, url):
        if payload.get("x402Version") != 2 or payload.get("accepted") != requirements or payload.get("resource", {}).get("url") != url:
            raise InvalidPayment("demo_payment_terms_mismatch")
        if payload.get("payload", {}).get("simulation") is not True:
            raise InvalidPayment("demo_payload_required")
        nonce = payload["payload"].get("nonce", "")
        if not isinstance(nonce, str) or not 16 <= len(nonce) <= 128:
            raise InvalidPayment("invalid_demo_nonce")
        txid = "DEMO-" + hashlib.sha256(nonce.encode()).hexdigest()[:52]
        return PaymentIdentity(txid, "DEMO-PAYER", 0)

    def verify(self, payload, requirements, identity):
        return None

    def settle(self, payload, requirements, identity):
        self.settle_calls += 1
        self.confirmations[identity.transaction_id] = {"round": 0, "source": "offline_simulation"}
        if self.store: self.store.demo_set(identity.transaction_id, self.confirmations[identity.transaction_id])
        return {"success": True, "transaction": identity.transaction_id, "network": "demo:local", "payer": identity.payer}

    def confirmed(self, payment_id):
        return self.confirmations.get(payment_id) or (self.store.demo_get(payment_id) if self.store else None)

# ---- SERVICE ----
import hashlib
import hmac
import json
import secrets
import uuid
from fastapi import HTTPException


def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def public_plan(plan): return {k: v for k, v in plan.items() if k not in ("cost_units", "package_code")}
def public_price(price): return {k: v for k, v in price.items() if k != "internal"}


class Service:
    def __init__(self, cfg, store, provider, gateway):
        self.cfg, self.store, self.provider, self.gateway = cfg, store, provider, gateway
        self.vault = Vault(cfg); self.signer = ReceiptSigner(cfg); self.pricing = Pricing(cfg)

    def authorize(self, row, token):
        if not row or not token or not hmac.compare_digest(row["token_hash"], token_hash(token)):
            raise HTTPException(404, "Pedido no encontrado o código de recuperación incorrecto")
        if row["mode"] != self.cfg.mode: raise HTTPException(409, "El pedido pertenece a otra modalidad de red")
        return row

    def parent_profile(self, parent):
        if not parent or parent["status"] != "completed": raise HTTPException(409, "La eSIM original todavía no está disponible")
        d = self.vault.open(parent["delivery"])
        return d["profile_id"], d["iccid"]

    def catalog(self, country, parent=None, fresh=False):
        if country not in self.cfg.allowed_countries: raise HTTPException(400, "Destino no habilitado")
        profile = self.parent_profile(parent)[1] if parent else None
        result = []
        for plan in self.provider.plans(country, profile, fresh):
            price = self.pricing.calculate(plan)
            if price:
                result.append({"plan": public_plan(plan), "pricing": public_price(price), "features_sha256": digest(comparable(plan))})
        return sorted(result, key=lambda x: int(x["pricing"]["amount_atomic"]))

    def quote(self, params, oid, token, parent_token=None):
        try:
            if str(uuid.UUID(oid)) != oid: raise ValueError()
        except (ValueError, TypeError): raise HTTPException(400, "Idempotency-Key debe ser un UUID")
        if not token or not 32 <= len(token) <= 128 or not token.isascii(): raise HTTPException(400, "X-Recovery-Token debe contener 32–128 caracteres ASCII")
        old = self.store.get(oid)
        if old:
            self.authorize(old, token)
            if old["request_hash"] != digest(params): raise HTTPException(409, "Este identificador pertenece a otro pedido")
            return old
        if self.cfg.mode == "mainnet" and not self.cfg.sales_enabled: raise HTTPException(503, "La tienda todavía no acepta compras reales")
        country = params["country"]
        if country not in self.cfg.allowed_countries: raise HTTPException(400, "Destino no habilitado")
        parent = None
        if params["kind"] == "topup":
            parent = self.authorize(self.store.get(params.get("parent_id")), parent_token)
            if json.loads(parent["request_json"])["kind"] != "purchase": raise HTTPException(400, "Usa el pedido original de la eSIM")
            if json.loads(parent["request_json"])["country"] != country: raise HTTPException(400, "Usa el destino de la eSIM original")
        elif params.get("parent_id"): raise HTTPException(400, "parent_id sólo se usa en recargas")
        profile = self.parent_profile(parent)[1] if parent else None
        matches = [x for x in self.provider.plans(country, profile, fresh=True) if x["id"] == params["plan_id"]]
        if len(matches) != 1: raise HTTPException(404, "Paquete no disponible o no compatible con esta eSIM")
        plan = matches[0]; price = self.pricing.calculate(plan)
        if not price: raise HTTPException(409, "No podemos ofrecer un precio competitivo con el margen configurado")
        if self.provider.balance() < plan["cost_units"]: raise HTTPException(503, "No hay saldo suficiente para emitir esta eSIM; no se ha cobrado")
        cfg = self.cfg
        terms = {"scheme": "exact", "network": cfg.network, "asset": cfg.asset, "amount": price["amount_atomic"],
                 "payTo": cfg.pay_to, "maxTimeoutSeconds": cfg.quote_ttl,
                 "extra": {"decimals": 6, **({"tag": "x402-global-challenge"} if cfg.mode == "mainnet" else {})}}
        quote = {"plan": plan, "pricing": price, "terms": terms, "resource_url": cfg.public_url + "/api/pay"}
        values = {"id": oid, "token_hash": token_hash(token), "request_hash": digest(params), "request_json": canonical(params),
                  "quote_json": canonical(quote), "status": "quoted", "mode": cfg.mode, "created_ms": now_ms(),
                  "updated_ms": now_ms(), "expires_ms": now_ms() + cfg.quote_ttl * 1000,
                  "provider_transaction": "c402-" + oid, "parent_id": params.get("parent_id")}
        if not self.store.insert(values):
            old = self.authorize(self.store.get(oid), token)
            if old["request_hash"] != digest(params): raise HTTPException(409, "Conflicto de pedido")
            return old
        self.store.audit(oid, "quote_created")
        return self.store.get(oid)

    def challenge(self, row):
        q = json.loads(row["quote_json"])
        return {"x402Version": 2, "resource": {"url": q["resource_url"], "mimeType": "application/json",
                    "description": "Purchase mobile eSIM data or a compatible top-up; retrieve the same order without repaying."},
                "accepts": [q["terms"]], "extensions": {"bazaar": {"info": {"input": {"type": "http", "method": "POST", "bodyType": "json", "body": {"order_id": "UUID from POST /api/orders"}},
                    "output": {"type": "json", "example": {"status": "completed", "delivery": {"activation_code": "private eSIM code"}}}},
                    "schema": {"type": "object", "properties": {"input": {"type": "object"}, "output": {"type": "object"}}, "required": ["input"]}}}}

    def view(self, row):
        if row["result"]:
            result = self.vault.open(row["result"])
            if row["status"] == "refunded": result = {**result, "current_status": "refunded", "refund_transaction": row["refund_tx"]}
            return result
        q = json.loads(row["quote_json"])
        return {"order_id": row["id"], "status": row["status"], "simulation": self.cfg.simulation,
                "network": self.cfg.network, "request": json.loads(row["request_json"]), "plan": public_plan(q["plan"]),
                "pricing": public_price(q["pricing"]), "expires_ms": row["expires_ms"], "error_code": row["error_code"],
                "payment": json.loads(row["payment_json"]) if row["payment_json"] else None,
                "refund_transaction": row["refund_tx"], "support_email": self.cfg.support_email,
                "fulfillment": self.fulfillment(row),
                "next_action": "recover_same_order" if row["status"] not in ("quoted", "expired") else "quote_or_pay"}

    def fulfillment(self, row):
        # Authenticated order responses only. Never include credentials or activation codes here.
        history = self.store.history(row["id"]) if row["payment_json"] else []
        accepted = next((e["at_ms"] for e in history if e["event"] == "provider_order_accepted"), None)
        paid = next((e["at_ms"] for e in history if e["event"] == "payment_confirmed"), None)
        started = accepted or paid
        return {"provider_order": row["provider_order"], "provider_transaction": row["provider_transaction"],
                "provider_accepted_ms": accepted, "payment_confirmed_ms": paid,
                "expected_provider_seconds": 30, "delayed": bool(started and now_ms() - started > 120000),
                "error_code": row["error_code"]}

    def delivery_issue(self, row, code):
        # Persist a bounded machine-readable code; never log provider bodies, keys or LPA codes.
        import logging
        import re
        code = code if re.fullmatch(r"[a-zA-Z0-9_]{1,90}", code) else "provider_unavailable"
        if row["error_code"] != code:
            if self.store.change(row["id"], ["issuing"], {"error_code": code}):
                self.store.audit(row["id"], "delivery_check_" + code[:60])
                logging.getLogger("cryptoesim").warning("delivery_check order=%s code=%s", row["id"], code)
        return self.store.get(row["id"])

    def pay(self, row, raw):
        if row["status"] == "completed": return row
        if row["status"] in ("expired", "refund_required", "refunding", "refunded", "needs_review"): return row
        if row["status"] == "verifying":
            if now_ms() - row["updated_ms"] < 120000: return row
            self.store.change(row["id"], ["verifying"], {"status": "quoted", "claim": None}, row["claim"])
            row = self.store.get(row["id"])
        if row["status"] == "quoted":
            if self.cfg.mode == "mainnet" and not self.cfg.sales_enabled:
                raise HTTPException(503, "Las ventas están pausadas; el pago no se ha enviado")
            if now_ms() > row["expires_ms"]:
                self.store.change(row["id"], ["quoted"], {"status": "expired"}); return self.store.get(row["id"])
            if not raw: return row
            claim = str(uuid.uuid4())
            if not self.store.change(row["id"], ["quoted"], {"status": "verifying", "claim": claim}): return self.store.get(row["id"])
            q = json.loads(row["quote_json"]); req = json.loads(row["request_json"])
            try:
                payload = decode_header(raw)
                identity = self.gateway.inspect(payload, q["terms"], q["resource_url"])
                self.gateway.verify(payload, q["terms"], identity)
                iccid = self.parent_profile(self.store.get(row["parent_id"]))[1] if row["parent_id"] else None
                current = [p for p in self.provider.plans(req["country"], iccid, fresh=True) if p["id"] == q["plan"]["id"]]
                if len(current) != 1 or digest(current[0]) != digest(q["plan"]):
                    self.store.change(row["id"], ["verifying"], {"status": "expired", "error_code": "catalog_changed_before_payment"}, claim)
                    return self.store.get(row["id"])
                if self.provider.balance() < q["plan"]["cost_units"]: raise ProviderUnavailable("insufficient_supplier_balance")
                if now_ms() > row["expires_ms"]:
                    self.store.change(row["id"], ["verifying"], {"status": "expired"}, claim); return self.store.get(row["id"])
                if not self.store.change(row["id"], ["verifying"], {"status": "prepared", "payment_payload": self.vault.seal(payload),
                        "payment_id": identity.transaction_id, "payer": identity.payer, "claim": None}, claim):
                    raise InvalidPayment("payment_already_used")
                self.store.audit(row["id"], "signed_payment_persisted")
            except (InvalidPayment, ValueError, TypeError):
                self.store.change(row["id"], ["verifying"], {"status": "quoted", "error_code": "invalid_payment", "claim": None}, claim)
                raise HTTPException(400, "Pago inválido o ya utilizado. Conserva el estado del pedido.")
            except (ProviderUnavailable, ProviderRejected, PaymentUnavailable):
                self.store.change(row["id"], ["verifying"], {"status": "quoted", "error_code": "preflight_unavailable", "claim": None}, claim)
                raise HTTPException(503, "No se ha enviado el pago; recupera este mismo pedido")
            row = self.store.get(row["id"])
        return self.advance(row)

    def advance(self, row):
        oid = row["id"]
        if row["mode"] != self.cfg.mode: return row
        if row["status"] == "prepared":
            if now_ms() > row["expires_ms"]:
                self.store.change(oid, ["prepared"], {"status": "expired", "error_code": "payment_not_submitted"}); return self.store.get(oid)
            if not self.store.change(oid, ["prepared"], {"status": "paying"}): return self.store.get(oid)
            row = self.store.get(oid)
            payload = self.vault.open(row["payment_payload"]); q = json.loads(row["quote_json"])
            identity = self.gateway.inspect(payload, q["terms"], q["resource_url"])
            try: self.gateway.settle(payload, q["terms"], identity)
            except PaymentUnavailable: pass
            self.store.change(oid, ["paying"], {"status": "payment_pending"})
            row = self.store.get(oid)
        if row["status"] in ("paying", "payment_pending"):
            confirmed = self.gateway.confirmed(row["payment_id"])
            if confirmed is None and now_ms() - row["updated_ms"] > 60000:
                # Recover a crash before/after the original settlement call. Reuse the
                # identical signed transfer: Algorand cannot charge this txid twice.
                claim = str(uuid.uuid4())
                if self.store.change(oid, [row["status"]], {"status": "paying", "claim": claim}, row["claim"]):
                    q = json.loads(row["quote_json"]); payload = self.vault.open(row["payment_payload"])
                    try:
                        identity = self.gateway.inspect(payload, q["terms"], q["resource_url"])
                        self.gateway.settle(payload, q["terms"], identity)
                    except (PaymentUnavailable, InvalidPayment): pass
                    self.store.change(oid, ["paying"], {"status": "payment_pending", "claim": None}, claim)
                    row = self.store.get(oid)
                    confirmed = self.gateway.confirmed(row["payment_id"])
            if confirmed is None: return row
            payment = {"success": True, "transaction": row["payment_id"], "network": self.cfg.network, "payer": row["payer"]}
            if self.store.change(oid, ["paying", "payment_pending"], {"status": "paid", "payment_json": canonical(payment),
                                  "confirmed_round": confirmed["round"], "error_code": None}): self.store.audit(oid, "payment_confirmed")
            row = self.store.get(oid)
        if row["status"] == "paid":
            claim = str(uuid.uuid4())
            if not self.store.change(oid, ["paid"], {"status": "ordering", "claim": claim}): return self.store.get(oid)
            row = self.store.get(oid)
            return self.submit_provider(row)
        if row["status"] == "ordering" and now_ms() - row["updated_ms"] > 120000:
            # A lost base-order response may be retried with the documented idempotent transactionId.
            # Top-up idempotency is not explicitly guaranteed in the docs: never retry it blindly.
            kind = json.loads(row["request_json"])["kind"]
            if kind == "topup":
                self.store.change(oid, ["ordering"], {"status": "needs_review", "error_code": "topup_outcome_unknown"}, row["claim"])
                return self.store.get(oid)
            claim = str(uuid.uuid4())
            if self.store.change(oid, ["ordering"], {"claim": claim}, row["claim"]): return self.submit_provider(self.store.get(oid))
        if row["status"] == "issuing":
            try:
                if not row["provider_order"]: return self.delivery_issue(row, "missing_provider_order")
                p = self.provider.profile(order_no=row["provider_order"])
                if p:
                    if p.get("transactionId") not in (None, row["provider_transaction"]): raise ProviderUnavailable("provider_identity_mismatch")
                    if not p.get("esimTranNo") or not p.get("iccid") or not p.get("ac"):
                        return self.delivery_issue(row, "provider_profile_incomplete")
                    if not self.cfg.simulation and not p["ac"].startswith("LPA:1$"): raise ProviderUnavailable("invalid_activation_code")
                    plan = json.loads(row["quote_json"])["plan"]
                    if int(p.get("totalVolume", 0)) < plan["volume_bytes"] or int(p.get("totalDuration", 0)) < plan["duration_days"]:
                        self.store.change(oid, ["issuing"], {"status": "needs_review", "error_code": "delivered_allowance_mismatch"})
                        return self.store.get(oid)
                    delivery = {"provider": "demo" if self.cfg.simulation else "esim_access", "provider_order": row["provider_order"],
                        "provider_transaction": row["provider_transaction"], "profile_id": p["esimTranNo"], "iccid": p["iccid"],
                        "activation_code": p["ac"], "apn": p.get("apn", ""), "esim_status": p.get("esimStatus"),
                        "total_bytes": int(p["totalVolume"]), "duration_days": p.get("totalDuration"),
                        "expires_at": p.get("expiredTime"), "simulation": self.cfg.simulation}
                    return self.finish(row, delivery)
                return self.delivery_issue(row, "provider_profile_pending")
            except ProviderRejected as exc:
                return self.delivery_issue(row, "provider_" + exc.code)
            except ProviderUnavailable as exc:
                return self.delivery_issue(row, str(exc))
            except (ValueError, TypeError, KeyError, AttributeError):
                return self.delivery_issue(row, "malformed_profile_response")
        return self.store.get(oid)

    def submit_provider(self, row):
        q = json.loads(row["quote_json"]); req = json.loads(row["request_json"]); oid = row["id"]
        try:
            if req["kind"] == "purchase":
                number = self.provider.order(row["provider_transaction"], q["plan"])
                self.store.change(oid, ["ordering"], {"status": "issuing", "provider_order": number, "claim": None, "error_code": None}, row["claim"])
                self.store.audit(oid, "provider_order_accepted")
                import logging
                logging.getLogger("cryptoesim").warning("provider_order_accepted order=%s", oid)
                return self.advance(self.store.get(oid))
            parent = self.store.get(row["parent_id"])
            profile, iccid = self.parent_profile(parent)
            obj = self.provider.topup(row["provider_transaction"], q["plan"], profile)
            if str(obj.get("iccid")) != str(iccid): raise ProviderUnavailable("topup_identity_mismatch")
            delivery = {"provider": "demo" if self.cfg.simulation else "esim_access", "provider_order": parent["provider_order"],
                "provider_transaction": row["provider_transaction"], "profile_id": profile, "iccid": iccid,
                "topup_reference": obj.get("topUpEsimTranNo"), "total_bytes": int(obj["totalVolume"]),
                "duration_days": obj.get("totalDuration"), "expires_at": obj.get("expiredTime"), "simulation": self.cfg.simulation}
            return self.finish(row, delivery)
        except ProviderRejected as exc:
            # 200010 means async allocation. Server/busy/unknown codes do not prove rejection.
            known_rejections = {"200005", "200006", "200007", "200011", "310241", "310243", "310403", "200002"}
            if exc.code in known_rejections:
                self.store.change(oid, ["ordering"], {"status": "refund_required", "error_code": "provider_" + exc.code}, row["claim"])
                self.store.audit(oid, "refund_required")
            elif req["kind"] == "topup":
                self.store.change(oid, ["ordering"], {"status": "needs_review", "error_code": "topup_outcome_unknown"}, row["claim"])
            else:
                code = exc.code if exc.code.isdecimal() and len(exc.code) <= 12 else "unknown"
                self.store.change(oid, ["ordering"], {"error_code": "provider_" + code}, row["claim"])
            import logging
            logging.getLogger("cryptoesim").warning("provider_order_failed order=%s code=%s", oid, self.store.get(oid)["error_code"])
        except (ProviderUnavailable, ValueError, TypeError, KeyError):
            if req["kind"] == "topup":
                self.store.change(oid, ["ordering"], {"status": "needs_review", "error_code": "topup_outcome_unknown"}, row["claim"])
            else:
                self.store.change(oid, ["ordering"], {"error_code": "provider_outcome_unknown"}, row["claim"])
        return self.store.get(oid)

    def finish(self, row, delivery):
        q = json.loads(row["quote_json"])
        bundle = {"order_id": row["id"], "status": "completed", "simulation": self.cfg.simulation,
                  "request": json.loads(row["request_json"]), "plan": public_plan(q["plan"]),
                  "pricing": public_price(q["pricing"]), "delivery": delivery, "payment": json.loads(row["payment_json"])}
        payload = {"schema": "cryptoesim.receipt.v1", "order_id": row["id"], "simulation": self.cfg.simulation,
                   "network": self.cfg.network, "transaction_id": row["payment_id"], "pay_to": q["terms"]["payTo"],
                   "asset": q["terms"]["asset"], "amount_atomic": q["terms"]["amount"], "confirmed_round": row["confirmed_round"],
                   "issued_ms": now_ms(), **{k + "_sha256": digest(bundle[k]) for k in ("request", "plan", "pricing", "delivery", "payment")}}
        bundle["receipt"] = self.signer.sign(payload)
        if self.store.change(row["id"], ["issuing", "ordering", "needs_review"], {"status": "completed", "delivery": self.vault.seal(delivery),
                              "result": self.vault.seal(bundle), "error_code": None, "claim": None}): self.store.audit(row["id"], "delivery_ready")
        return self.store.get(row["id"])

    def tick(self):
        for row in self.store.list(["prepared", "paying", "payment_pending", "paid", "ordering", "issuing"], 30):
            if now_ms() - row["updated_ms"] < 5000: continue
            try: self.advance(row)
            except Exception:
                # The persisted state is retained. No secrets or provider responses in logs.
                import logging
                logging.getLogger("cryptoesim").error("recovery_failed order=%s", row["id"])

# ---- HTTP APPLICATION ----
import asyncio
import hmac
import io
import json
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from sqlalchemy import text


ROOT = Path(__file__).parent
WEB = ROOT.parent / "cryptoesim-storefront"


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["purchase", "topup"] = "purchase"
    plan_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    country: str = Field(pattern=r"^[A-Z]{2}$")
    parent_id: str | None = Field(default=None, max_length=36)
    compatible_device: Literal[True]
    terms_accepted: Literal[True]


def create_app(cfg=None, store=None, provider=None, gateway=None):
    cfg = (cfg or Settings.from_env()).validate()
    db = store or Store(cfg.database_url)
    provider = provider or (DemoProvider(db) if cfg.simulation else ESIMAccess(cfg))
    gateway = gateway or (DemoGateway(db) if cfg.mode == "demo" else LiveGateway(cfg))
    service = Service(cfg, db, provider, gateway)

    @asynccontextmanager
    async def lifespan(app):
        async def work():
            while True:
                await asyncio.sleep(15)
                await asyncio.to_thread(service.tick)
        task = asyncio.create_task(work()) if cfg.worker_enabled else None
        yield
        if task:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass

    app = FastAPI(title="CryptoEsim", version="2.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service; app.state.settings = cfg
    traffic = defaultdict(deque)

    @app.middleware("http")
    async def security(request, call_next):
        if request.url.path.startswith("/api/"):
            key = request.client.host if request.client else "local"
            now = time.monotonic(); q = traffic[key]
            while q and q[0] < now - 60: q.popleft()
            if len(q) >= 120: return JSONResponse({"detail": "Espera un minuto antes de continuar"}, 429, headers={"Retry-After": "60"})
            q.append(now)
            if len(traffic) > 10000:
                for k in list(traffic):
                    if not traffic[k] or traffic[k][-1] < now - 60: del traffic[k]
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 32768: return JSONResponse({"detail": "Petición demasiado grande"}, 413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https: wss:; frame-src https:; object-src 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.exception_handler(ProviderUnavailable)
    async def unavailable(_, exc): return JSONResponse({"detail": "El proveedor no está disponible. Conserva tu pedido y reintenta la consulta."}, 503)
    @app.exception_handler(ProviderRejected)
    async def rejected(_, exc): return JSONResponse({"detail": "El proveedor no ha aceptado la consulta", "code": exc.code}, 503)

    def token(request): return request.headers.get("Authorization", "").removeprefix("Bearer ") or request.headers.get("X-Recovery-Token", "")
    def own(oid, request): return service.authorize(db.get(oid), token(request))
    def admin(request):
        if not cfg.admin_token or not hmac.compare_digest(token(request), cfg.admin_token): raise HTTPException(401, "Acceso de operador requerido")
    def order_response(row, challenge=False):
        obj = service.view(row); headers = {"X-Order-ID": row["id"]}
        code = 200 if row["status"] in ("completed", "refunded") else 202
        if row["payment_json"]: headers["PAYMENT-RESPONSE"] = encode_header(json.loads(row["payment_json"]))
        if row["status"] == "quoted" and challenge:
            value = service.challenge(row); headers["PAYMENT-REQUIRED"] = encode_header(value); obj["challenge"] = value; code = 402
        elif row["status"] == "expired": code = 410
        if code == 202: headers["Retry-After"] = "5"
        return JSONResponse(obj, code, headers=headers)

    @app.get("/")
    def home():
        if (WEB / "cryptoesim.html").is_file(): return FileResponse(WEB / "cryptoesim.html")
        return {"service": "CryptoEsim API", "health": "/health"}
    @app.get("/docs")
    def api_docs(): return {"paid_resource": cfg.public_url + "/api/pay", "catalog": "/api/plans", "orders": "/api/orders"}
    @app.get("/health")
    def health():
        with db.engine.connect() as c: c.execute(text("SELECT 1"))
        return {"ok": True, "mode": cfg.mode, "simulation": cfg.simulation, "sales_enabled": cfg.mode != "mainnet" or cfg.sales_enabled}
    @app.get("/.well-known/cryptoesim-key.json")
    def signing_key(): return service.signer.public_document()
    @app.get("/api/config")
    def config():
        return {"mode": cfg.mode, "network": cfg.network, "asset": cfg.asset, "pay_to": cfg.pay_to, "public_url": cfg.public_url,
                "simulation": cfg.simulation, "sales_enabled": cfg.mode != "mainnet" or cfg.sales_enabled,
                "countries": cfg.allowed_countries, "merchant_name": cfg.merchant_name, "support_email": cfg.support_email,
                "algod_url": cfg.node_url if cfg.mode != "demo" else None, "signing_key": service.signer.public_document(),
                "delivery_refresh": True,
                "terms_version": "cryptoesim-1", "usage_delay_hours": "2–3"}
    @app.get("/api/plans")
    def plans(country: str = "ES"):
        return {"simulation": cfg.simulation, "items": service.catalog(country)}
    @app.post("/api/orders")
    def quote(body: OrderInput, request: Request):
        oid = request.headers.get("Idempotency-Key") or str(uuid.uuid4())
        access = request.headers.get("X-Recovery-Token") or secrets.token_urlsafe(32)
        row = service.quote(body.model_dump(), oid, access, request.headers.get("X-Parent-Token"))
        response = order_response(row, True)
        response.headers["X-Recovery-Token"] = access
        return response
    @app.post("/api/orders/{oid}/pay")
    def pay(oid: str, request: Request):
        row = own(oid, request); was_completed = row["status"] == "completed"
        row = service.pay(row, request.headers.get("PAYMENT-SIGNATURE"))
        response = order_response(row, True); response.headers["X-Replayed"] = str(was_completed).lower()
        return response
    @app.post("/api/pay")
    def pay_resource(body: dict, request: Request):
        # A stable resource URL keeps discovery and leaderboard records together.
        oid = body.get("order_id")
        if not isinstance(oid, str): raise HTTPException(400, "Crea un pedido en /api/orders e indica order_id")
        return pay(oid, request)
    @app.get("/api/orders/{oid}")
    def get_order(oid: str, request: Request): return order_response(own(oid, request))
    @app.post("/api/orders/{oid}/delivery")
    def refresh_delivery(oid: str, request: Request):
        row = own(oid, request)
        # Only query an already-created supplier order. Never settle a payment or create an eSIM.
        if row["status"] == "issuing" and row["payment_json"] and row["provider_order"]:
            row = service.advance(row)
        return order_response(row)
    @app.post("/api/orders/{oid}/resume")
    def resume(oid: str, request: Request): return order_response(service.advance(own(oid, request)))
    @app.get("/api/orders/{oid}/events")
    def order_events(oid: str, request: Request): own(oid, request); return {"events": db.history(oid)}
    @app.get("/api/orders/{oid}/qr")
    def qr(oid: str, request: Request):
        import qrcode
        import qrcode.image.svg
        row = own(oid, request)
        if row["status"] != "completed": raise HTTPException(409, "La eSIM aún no está lista")
        d = service.vault.open(row["delivery"])
        if not d.get("activation_code"): raise HTTPException(400, "La recarga utiliza la eSIM original")
        image = qrcode.make(d["activation_code"], image_factory=qrcode.image.svg.SvgPathImage)
        out = io.BytesIO(); image.save(out)
        return Response(out.getvalue(), media_type="image/svg+xml")
    @app.get("/api/orders/{oid}/usage")
    def usage(oid: str, request: Request):
        row = own(oid, request); profile, _ = service.parent_profile(row)
        return provider.usage(profile)
    @app.get("/api/orders/{oid}/topup-plans")
    def topup_plans(oid: str, request: Request):
        row = own(oid, request)
        return {"simulation": cfg.simulation, "items": service.catalog(json.loads(row["request_json"])["country"], row)}
    @app.post("/api/orders/{oid}/demo-consume")
    def consume(oid: str, request: Request):
        if not cfg.simulation: raise HTTPException(404)
        row = own(oid, request); profile, _ = service.parent_profile(row)
        provider.consume(profile, 900 * 1024 * 1024)
        return provider.usage(profile)
    @app.get("/api/admin/orders")
    def admin_orders(request: Request):
        admin(request)
        return {"orders": [{k: r[k] for k in ("id", "status", "mode", "created_ms", "updated_ms", "payment_id", "provider_order", "error_code", "refund_tx")} for r in db.list(limit=200)]}
    @app.get("/api/admin/orders/{oid}/refund-plan")
    def refund_plan(oid: str, request: Request):
        admin(request); row = db.get(oid)
        if not row or row["status"] not in ("refund_required", "refunding", "refunded"): raise HTTPException(409, "Pedido no elegible para reembolso automático")
        terms = json.loads(row["quote_json"])["terms"]
        return {"order_id": oid, "status": row["status"], "network": cfg.network, "sender": cfg.pay_to, "recipient": row["payer"],
                "asset": cfg.asset, "amount_atomic": terms["amount"], "refund_transaction": row["refund_tx"], "note": "cryptoesim-refund:" + oid}
    @app.post("/api/admin/orders/{oid}/resolve-review")
    def resolve_review(oid: str, body: dict, request: Request):
        admin(request); row = db.get(oid)
        if not row or row["status"] != "needs_review": raise HTTPException(409, "El pedido no está pendiente de revisión")
        reference = body.get("supplier_confirmation", "")
        if body.get("operator_verified_with_supplier") is not True or not isinstance(reference, str) or not 8 <= len(reference) <= 150:
            raise HTTPException(400, "Confirma la consulta al proveedor e indica su referencia de soporte")
        if body.get("outcome") == "supplier_confirmed_not_issued":
            if not db.change(oid, ["needs_review"], {"status": "refund_required", "error_code": "operator_confirmed_not_issued"}): raise HTTPException(409, "Otro operador modificó el pedido")
            db.audit(oid, "operator_confirmed_refund_required")
        elif body.get("outcome") == "supplier_confirmed_topup":
            if json.loads(row["request_json"])["kind"] != "topup": raise HTTPException(400, "Esta acción sólo resuelve recargas")
            parent = db.get(row["parent_id"]); profile, iccid = service.parent_profile(parent)
            p = provider.profile(profile_id=profile)
            if not p or p.get("iccid") != iccid: raise HTTPException(409, "El perfil no coincide")
            quoted = json.loads(row["quote_json"])["plan"]
            if int(p.get("totalVolume", 0)) < int(service.vault.open(parent["delivery"])["total_bytes"]) + quoted["volume_bytes"]:
                raise HTTPException(409, "El proveedor todavía no muestra el volumen adicional")
            service.finish(row, {"provider": "demo" if cfg.simulation else "esim_access", "provider_order": parent["provider_order"],
                "provider_transaction": row["provider_transaction"], "profile_id": profile, "iccid": iccid,
                "topup_reference": reference, "total_bytes": int(p["totalVolume"]), "duration_days": p.get("totalDuration"),
                "expires_at": p.get("expiredTime"), "simulation": cfg.simulation, "verification": "operator_attested_supplier_confirmation"})
            db.audit(oid, "topup_manually_confirmed")
        else: raise HTTPException(400, "Resultado de revisión desconocido")
        return order_response(db.get(oid))
    @app.post("/api/admin/orders/{oid}/reserve-refund")
    def reserve_refund(oid: str, body: dict, request: Request):
        admin(request); row = db.get(oid)
        if not row or row["status"] not in ("refund_required", "refunding", "refunded"): raise HTTPException(409, "Reembolso no solicitado")
        txid = body.get("transaction", "")
        if not isinstance(txid, str) or not (txid.startswith("DEMO-REFUND-") and len(txid) <= 64 if cfg.mode == "demo" else len(txid) == 52 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in txid)):
            raise HTTPException(400, "TXID de reembolso inválido")
        if row["status"] == "refund_required":
            db.change(oid, ["refund_required"], {"status": "refunding", "refund_tx": txid})
            row = db.get(oid)
        if row["refund_tx"] != txid: raise HTTPException(409, "Ya hay otra transacción reservada; recupera su archivo original")
        return {"status": row["status"], "transaction": row["refund_tx"]}
    @app.post("/api/admin/orders/{oid}/record-refund")
    def record_refund(oid: str, body: dict, request: Request):
        admin(request); row = db.get(oid)
        if not row or row["status"] not in ("refunding", "refunded"): raise HTTPException(409, "Reserva la transacción antes de emitir el reembolso")
        txid = body.get("transaction", "")
        if txid != row["refund_tx"]: raise HTTPException(409, "La transacción no coincide con la reservada")
        if row["status"] == "refunded":
            if txid != row["refund_tx"]: raise HTTPException(409, "Reembolso ya registrado")
            return {"status": "refunded", "transaction": txid}
        terms = json.loads(row["quote_json"])["terms"]
        if cfg.mode == "demo":
            if not txid.startswith("DEMO-REFUND-"): raise HTTPException(400, "Identificador de simulación requerido")
        else:
            import base64
            import httpx
            if len(txid) != 52 or not txid.isalnum(): raise HTTPException(400, "TXID inválido")
            try:
                r = httpx.get(cfg.history_url + "/v2/transactions/" + txid, timeout=15); r.raise_for_status()
                tx = r.json()["transaction"]; transfer = tx["asset-transfer-transaction"]
                valid = (tx["id"] == txid and tx.get("confirmed-round", 0) > 0
                    and tx["sender"] == cfg.pay_to and transfer["receiver"] == row["payer"]
                    and str(transfer["asset-id"]) == cfg.asset and str(transfer["amount"]) == terms["amount"]
                    and base64.b64decode(tx.get("note", "")).decode() == "cryptoesim-refund:" + oid
                    and not tx.get("rekey-to") and not transfer.get("close-to"))
                if not valid: raise ValueError("refund_mismatch")
            except Exception: raise HTTPException(409, "La cadena todavía no confirma este reembolso con los importes correctos")
        if not db.change(oid, ["refunding"], {"status": "refunded"}): raise HTTPException(409, "Conflicto de reembolso")
        db.audit(oid, "refund_confirmed")
        return {"status": "refunded", "transaction": txid}

    if WEB.is_dir(): app.mount("/", StaticFiles(directory=WEB), name="storefront")
    app.add_middleware(CORSMiddleware, allow_origins=[cfg.store_origin] if cfg.store_origin else [], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Recovery-Token", "X-Parent-Token", "PAYMENT-SIGNATURE"], expose_headers=["PAYMENT-REQUIRED", "PAYMENT-RESPONSE", "X-Order-ID", "X-Recovery-Token", "X-Replayed", "Retry-After"])
    return app


app = create_app()

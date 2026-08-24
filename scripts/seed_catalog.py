"""
Seed script — deterministic demo data.

Creates:
- 50 products across 10 categories
- 500 synthetic historical orders (for graph analysis)
- Demo mandates for OpenAI and Anthropic agents

Uses random.seed(42) for reproducible results.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.db.models.order import Order, OrderItem
from app.db.models.mandate import Mandate
from app.db.models.audit_log import AuditLog
from app.db.models.payment import Payment
from app.db.models.webhook_event import WebhookEvent
from app.db.models.upsell import UpsellRecommendation
from app.db.models.processed_intent import ProcessedIntent
from app.core.security import CryptoService


# ─── Product Catalog ────────────────────────────────────────────────

PRODUCTS = [
    # Mechanical Keyboards (7 products)
    ("KB001", "Mechanical RGB Keyboard", "Cherry MX Blue switches, full RGB backlighting, aluminum frame", 349900, 17, "mechanical-keyboards"),
    ("KB002", "Compact Mechanical Keyboard 65%", "Hot-swappable Gateron Red switches, PBT keycaps", 549900, 12, "mechanical-keyboards"),
    ("KB003", "Budget Mechanical Keyboard", "Outemu Blue switches, rainbow LED, ABS keycaps", 199900, 25, "mechanical-keyboards"),
    ("KB004", "Premium Wireless Mechanical Keyboard", "Low-profile Kailh switches, Bluetooth 5.0, 200hr battery", 699900, 8, "mechanical-keyboards"),
    ("KB005", "TKL Mechanical Keyboard", "Cherry MX Brown, tenkeyless, white backlighting", 449900, 14, "mechanical-keyboards"),
    ("KB006", "Gaming Mechanical Keyboard", "Razer Green equivalent, macro keys, magnetic wrist rest", 599900, 10, "mechanical-keyboards"),
    ("KB007", "Ortholinear Mechanical Keyboard", "Kailh Box White, split layout, programmable layers", 799900, 5, "mechanical-keyboards"),

    # Membrane Keyboards (3 products)
    ("MK001", "Standard Membrane Keyboard", "Full-size, spill-resistant, quiet keys", 79900, 50, "membrane-keyboards"),
    ("MK002", "Wireless Membrane Keyboard", "2.4GHz wireless, slim profile, multimedia keys", 129900, 35, "membrane-keyboards"),
    ("MK003", "Ergonomic Membrane Keyboard", "Split design, integrated palm rest, quiet dome switches", 199900, 20, "membrane-keyboards"),

    # Mouse (7 products)
    ("MOUSE001", "Wireless Ergonomic Mouse", "2.4GHz, 6 buttons, DPI 800-3200, 18-month battery", 149900, 30, "mouse"),
    ("MOUSE002", "Gaming Mouse RGB", "16000 DPI, 8 programmable buttons, braided cable", 249900, 22, "mouse"),
    ("MOUSE003", "Vertical Ergonomic Mouse", "57-degree angle, 4 DPI levels, reduces wrist strain", 179900, 15, "mouse"),
    ("MOUSE004", "Compact Travel Mouse", "Bluetooth, ultra-slim, USB-C rechargeable", 99900, 40, "mouse"),
    ("MOUSE005", "Trackball Mouse", "34mm ball, 3 buttons, wired, precise control", 199900, 12, "mouse"),
    ("MOUSE006", "Silent Click Mouse", "Near-zero noise, 2.4GHz, 1600 DPI", 119900, 28, "mouse"),
    ("MOUSE007", "Ambidextrous Gaming Mouse", "12000 DPI, RGB, 6 buttons, both-hand design", 179900, 18, "mouse"),

    # Headphones (5 products)
    ("HP001", "Over-Ear Studio Headphones", "50mm drivers, closed-back, detachable cable", 299900, 20, "headphones"),
    ("HP002", "Wireless ANC Headphones", "Active noise cancellation, 30hr battery, Bluetooth 5.2", 499900, 15, "headphones"),
    ("HP003", "Gaming Headset 7.1", "Virtual surround sound, retractable mic, RGB", 349900, 18, "headphones"),
    ("HP004", "Budget Wired Earbuds", "In-ear, 10mm drivers, braided cable, microphone", 49900, 60, "headphones"),
    ("HP005", "Open-Back Audiophile Headphones", "Planar magnetic drivers, velour pads, 250 ohm", 899900, 6, "headphones"),

    # Webcams (4 products)
    ("WC001", "1080p Webcam", "Full HD, auto-focus, built-in microphone, privacy shutter", 199900, 25, "webcams"),
    ("WC002", "4K Streaming Webcam", "Ultra HD, 90° FOV, ring light, noise-canceling mic", 449900, 10, "webcams"),
    ("WC003", "Budget 720p Webcam", "HD ready, clip-on mount, plug and play", 79900, 45, "webcams"),
    ("WC004", "PTZ Conference Camera", "1080p, 3x zoom, remote control, wide-angle", 699900, 7, "webcams"),

    # Monitors (5 products)
    ("MON001", "27-inch 4K IPS Monitor", "3840x2160, 60Hz, 99% sRGB, USB-C, VESA mount", 2499900, 8, "monitors"),
    ("MON002", "24-inch FHD Monitor", "1920x1080, 75Hz, IPS, HDMI+VGA, eye-care", 999900, 15, "monitors"),
    ("MON003", "32-inch Curved Gaming Monitor", "2560x1440, 165Hz, VA panel, 1ms, FreeSync", 2999900, 5, "monitors"),
    ("MON004", "27-inch QHD Monitor", "2560x1440, 144Hz, IPS, height-adjustable", 1999900, 10, "monitors"),
    ("MON005", "Portable 15.6-inch Monitor", "1080p, USB-C, 300 nits, magnetic cover", 1499900, 12, "monitors"),

    # USB Hubs (4 products)
    ("HUB001", "7-in-1 USB-C Hub", "HDMI 4K, 3x USB-A, SD/microSD, PD 100W", 249900, 30, "usb-hubs"),
    ("HUB002", "4-Port USB 3.0 Hub", "Powered, aluminum, LED indicators", 99900, 40, "usb-hubs"),
    ("HUB003", "Docking Station USB-C", "Dual HDMI, Ethernet, 6x USB, PD 85W", 599900, 10, "usb-hubs"),
    ("HUB004", "Mini USB-C to USB-A Adapter", "OTG, 5Gbps, keychain design", 29900, 80, "usb-hubs"),

    # Microphones (4 products)
    ("MIC001", "USB Condenser Microphone", "Cardioid, 24-bit/96kHz, pop filter, desk stand", 299900, 20, "microphones"),
    ("MIC002", "Lapel Microphone", "Clip-on, omnidirectional, 3.5mm + USB-C adapter", 79900, 35, "microphones"),
    ("MIC003", "Dynamic Podcast Microphone", "XLR + USB, cardioid, built-in headphone amp", 499900, 10, "microphones"),
    ("MIC004", "Wireless Lavalier System", "2.4GHz, 200m range, 8hr battery, dual-channel", 399900, 12, "microphones"),

    # Laptop Stands (3 products)
    ("STAND001", "Aluminum Laptop Stand", "Adjustable height, ventilated, foldable, up to 17 inch", 199900, 25, "laptop-stands"),
    ("STAND002", "Laptop Cooling Pad", "5 fans, RGB lighting, adjustable angle, 2 USB ports", 149900, 30, "laptop-stands"),
    ("STAND003", "Vertical Laptop Dock", "Adjustable width, silicone grips, space-saving", 129900, 20, "laptop-stands"),

    # Cables (6 products)
    ("CBL001", "USB-C to USB-C Cable 2m", "100W PD, 10Gbps, braided nylon, E-marker", 59900, 60, "cables"),
    ("CBL002", "HDMI 2.1 Cable 3m", "8K@60Hz, 4K@120Hz, eARC, braided", 89900, 45, "cables"),
    ("CBL003", "Lightning to USB-C Cable", "MFi certified, 1.8m, fast charging", 99900, 50, "cables"),
    ("CBL004", "Ethernet Cat6a Cable 5m", "10Gbps, shielded, gold-plated, flat design", 49900, 55, "cables"),
    ("CBL005", "DisplayPort 1.4 Cable 2m", "8K@60Hz, HBR3, latching connector", 79900, 35, "cables"),
    ("CBL006", "USB-A to Micro-USB Cable", "Fast charge, 1m, braided, reversible USB-A", 29900, 70, "cables"),
]


def _generate_historical_orders(products: list[Product], count: int = 500) -> list[tuple[str, list[str]]]:
    """
    Generate synthetic historical orders with intentional co-purchase patterns.
    Returns list of (order_id, [sku1, sku2, ...]).
    """
    rng = random.Random(42)

    # Define intentional co-purchase patterns (for deterministic demo)
    # keyboard → mouse = ~41%, keyboard → wrist_rest ≈ N/A, keyboard → webcam = ~8%
    co_purchase_rules = {
        "mechanical-keyboards": [
            ("mouse", 0.41),           # 41% buy a mouse with keyboard
            ("headphones", 0.22),      # 22% buy headphones
            ("usb-hubs", 0.15),        # 15% buy a USB hub
            ("cables", 0.12),          # 12% buy cables
            ("webcams", 0.08),         # 8% buy a webcam
            ("laptop-stands", 0.06),   # 6% buy a stand
        ],
        "mouse": [
            ("mechanical-keyboards", 0.35),
            ("laptop-stands", 0.18),
            ("cables", 0.14),
        ],
        "headphones": [
            ("microphones", 0.30),
            ("cables", 0.20),
        ],
        "monitors": [
            ("cables", 0.45),
            ("usb-hubs", 0.35),
            ("webcams", 0.25),
        ],
    }

    # Group products by category
    by_category: dict[str, list[Product]] = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)

    orders = []
    for i in range(count):
        order_id = str(uuid.uuid4())
        # Pick a primary category
        primary_cat = rng.choice(list(by_category.keys()))
        primary_product = rng.choice(by_category[primary_cat])
        skus = [primary_product.sku]

        # Apply co-purchase rules
        rules = co_purchase_rules.get(primary_cat, [])
        for target_cat, prob in rules:
            if rng.random() < prob and target_cat in by_category:
                target_product = rng.choice(by_category[target_cat])
                if target_product.sku not in skus:
                    skus.append(target_product.sku)

        orders.append((order_id, skus))

    return orders


async def seed_all(db: AsyncSession) -> dict:
    """
    Seed the complete demo database.
    Deterministic via random.seed(42).
    """
    random.seed(42)

    # Clear existing data
    for model in [UpsellRecommendation, ProcessedIntent, WebhookEvent, Payment,
                  AuditLog, OrderItem, Order, Mandate, Product]:
        await db.execute(delete(model))

    await db.flush()

    # --- Seed Products ---
    products = []
    for sku, name, desc, price, stock, category in PRODUCTS:
        p = Product(
            sku=sku, name=name, description=desc,
            price_paise=price, stock_count=stock, category=category,
        )
        db.add(p)
        products.append(p)

    await db.flush()

    # --- Seed Historical Orders (for graph) ---
    historical = _generate_historical_orders(products, count=500)
    product_map = {p.sku: p for p in products}

    for order_id, skus in historical:
        total = sum(product_map[sku].price_paise for sku in skus)
        order = Order(
            id=order_id,
            agent_id="historical",
            mandate_id="historical",
            total_amount_paise=total,
            status="captured",
            idempotency_key=f"hist_{order_id}",
            receipt=f"hist_{order_id[:8]}",
        )
        db.add(order)

        for sku in skus:
            p = product_map[sku]
            item = OrderItem(
                order_id=order_id,
                product_id=p.id,
                sku=sku,
                quantity=1,
                unit_price_paise=p.price_paise,
                subtotal_paise=p.price_paise,
            )
            db.add(item)

    await db.flush()

    # --- Seed Mandates ---
    # OpenAI agent — ₹5,000 budget, keyboards + mouse
    openai_priv, openai_pub = CryptoService.generate_keypair()
    openai_scope = json.dumps({"sku": [], "category": ["mechanical-keyboards", "mouse", "cables"], "vendor": []})
    openai_mandate_id = "b7042ac0-1c11-446f-b3d2-3ad050026697" # Deterministic for testing
    canonical = CryptoService.build_mandate_canonical({
        "agent_id": "openai-demo-agent",
        "principal_id": "human-principal",
        "financial_ceiling_paise": 500000,
        "scope_values": openai_scope,
        "max_transactions": 5,
        "velocity_window_seconds": 86400,
    })
    openai_sig = CryptoService.sign(canonical, openai_priv)

    openai_mandate = Mandate(
        id=openai_mandate_id,
        agent_id="openai-demo-agent",
        principal_id="human-principal",
        financial_ceiling_paise=500000,
        scope_values=openai_scope,
        max_transactions=5,
        velocity_window_seconds=86400,
        signature=openai_sig,
        public_key=openai_pub,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(openai_mandate)

    # Anthropic agent — ₹2,500 budget, keyboards only
    anthropic_priv, anthropic_pub = CryptoService.generate_keypair()
    anthropic_scope = json.dumps({"sku": [], "category": ["mechanical-keyboards"], "vendor": []})
    anthropic_mandate_id = "b29e83db-ee84-4e4b-9651-03d7aa741a39" # Deterministic for testing
    canonical2 = CryptoService.build_mandate_canonical({
        "agent_id": "anthropic-demo-agent",
        "principal_id": "human-principal",
        "financial_ceiling_paise": 250000,
        "scope_values": anthropic_scope,
        "max_transactions": 3,
        "velocity_window_seconds": 86400,
    })
    anthropic_sig = CryptoService.sign(canonical2, anthropic_priv)

    anthropic_mandate = Mandate(
        id=anthropic_mandate_id,
        agent_id="anthropic-demo-agent",
        principal_id="human-principal",
        financial_ceiling_paise=250000,
        scope_values=anthropic_scope,
        max_transactions=3,
        velocity_window_seconds=86400,
        signature=anthropic_sig,
        public_key=anthropic_pub,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(anthropic_mandate)

    await db.flush()

    result = {
        "success": True,
        "products": len(products),
        "historical_orders": len(historical),
        "mandates": {
            "openai": {
                "mandate_id": openai_mandate_id,
                "agent_id": "openai-demo-agent",
                "budget": "₹5,000",
                "scope": "mechanical-keyboards, mouse, cables",
                "private_key": openai_priv,
            },
            "anthropic": {
                "mandate_id": anthropic_mandate_id,
                "agent_id": "anthropic-demo-agent",
                "budget": "₹2,500",
                "scope": "mechanical-keyboards",
                "private_key": anthropic_priv,
            },
        },
        "demo_product": {
            "sku": "KB001",
            "name": "Mechanical RGB Keyboard",
            "price": "₹3,499",
        },
        "expected_upsell": {
            "sku": "MOUSE001",
            "name": "Wireless Ergonomic Mouse",
            "expected_co_purchase_rate": "~41%",
        },
    }

    return result


# Allow running standalone
if __name__ == "__main__":
    import asyncio
    from app.db.session import init_db, get_session_factory, close_db

    async def main():
        await init_db()
        factory = get_session_factory()
        async with factory() as session:
            result = await seed_all(session)
            await session.commit()
            import json as _json
            print(_json.dumps(result, indent=2))
        await close_db()

    asyncio.run(main())

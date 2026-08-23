"""
Graph Upsell Engine — NetworkX-based co-purchase analysis.

Uses a synthetic order history to compute P(B|A) = count(A∩B) / count(A).
Only recommends when probability >= 40% AND support >= MIN_SUPPORT.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.order import Order, OrderItem
from app.db.models.product import Product
from app.db.models.upsell import UpsellRecommendation
from app.core.config import get_settings
from app.core.constants import UpsellStatus
from app.core.logging import get_logger

logger = get_logger("upsell_service")


class UpsellService:
    """Graph-based co-purchase recommendation engine."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._graph: nx.Graph | None = None

    async def build_graph(self) -> nx.Graph:
        """
        Build co-purchase graph from order history.
        Node = SKU, Edge weight = count of orders containing both SKUs.
        """
        graph = nx.Graph()

        # Fetch all order items grouped by order
        stmt = select(OrderItem.order_id, OrderItem.sku)
        result = await self.db.execute(stmt)
        rows = result.all()

        # Group SKUs by order
        order_skus: dict[str, list[str]] = defaultdict(list)
        for order_id, sku in rows:
            order_skus[order_id].append(sku)

        # Count co-purchases
        sku_counts: dict[str, int] = defaultdict(int)  # How many orders contain each SKU
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)

        for order_id, skus in order_skus.items():
            unique_skus = list(set(skus))
            for sku in unique_skus:
                sku_counts[sku] += 1

            for i in range(len(unique_skus)):
                for j in range(i + 1, len(unique_skus)):
                    pair = tuple(sorted([unique_skus[i], unique_skus[j]]))
                    pair_counts[pair] += 1

        # Build graph
        for sku, count in sku_counts.items():
            graph.add_node(sku, order_count=count)

        for (sku_a, sku_b), count in pair_counts.items():
            graph.add_edge(sku_a, sku_b, weight=count)

        self._graph = graph
        logger.info("Graph built", nodes=graph.number_of_nodes(), edges=graph.number_of_edges())
        return graph

    async def get_recommendation(
        self,
        source_sku: str,
        source_order_id: str,
        mandate_scope_categories: list[str] | None = None,
    ) -> UpsellRecommendation | None:
        """
        Generate a single upsell recommendation for a purchased SKU.

        Algorithm:
        1. Find purchased SKU in graph
        2. Find candidate neighbors
        3. Remove the purchased SKU
        4. Remove inactive/out-of-stock products
        5. Apply mandate scope
        6. Calculate P(B|A)
        7. Apply support threshold
        8. Sort by probability DESC, support DESC
        9. Select top candidate
        """
        if self._graph is None:
            await self.build_graph()

        graph = self._graph
        threshold = self.settings.upsell_probability_threshold
        min_support = self.settings.upsell_min_support

        # Step 1: Check if SKU is in graph
        if source_sku not in graph:
            logger.info("SKU not in graph", sku=source_sku)
            return None

        source_count = graph.nodes[source_sku].get("order_count", 0)

        # Check minimum support for source SKU
        if source_count < min_support:
            logger.info("Insufficient support for source SKU",
                        sku=source_sku, count=source_count, min=min_support)
            return None

        # Step 2-3: Get candidate neighbors
        candidates = []
        for neighbor in graph.neighbors(source_sku):
            if neighbor == source_sku:
                continue

            co_count = graph[source_sku][neighbor]["weight"]
            probability = co_count / source_count

            candidates.append({
                "sku": neighbor,
                "probability": probability,
                "support": co_count,
            })

        if not candidates:
            return None

        # Step 4: Filter out inactive/out-of-stock products
        filtered = []
        for c in candidates:
            product = await self._get_product(c["sku"])
            if product and product.is_active and product.stock_count > 0:
                c["product"] = product
                filtered.append(c)

        # Step 5: Apply mandate scope (if provided)
        if mandate_scope_categories:
            filtered = [
                c for c in filtered
                if c["product"].category in mandate_scope_categories
            ]

        # Step 6-7: Apply thresholds
        qualified = [c for c in filtered if c["probability"] >= threshold]

        if not qualified:
            logger.info("No candidates meet threshold",
                        sku=source_sku, threshold=threshold, checked=len(filtered))
            return None

        # Step 8: Sort
        qualified.sort(key=lambda c: (-c["probability"], -c["support"]))

        # Step 9: Select top
        best = qualified[0]
        product = best["product"]

        # Create recommendation record
        recommendation = UpsellRecommendation(
            id=str(uuid.uuid4()),
            source_order_id=source_order_id,
            source_sku=source_sku,
            recommended_sku=best["sku"],
            probability=round(best["probability"], 4),
            support_count=best["support"],
            confidence_score=round(best["probability"] * min(best["support"] / 100, 1.0), 4),
            status=UpsellStatus.PROPOSED.value,
            message=(
                f"{int(best['probability'] * 100)}% of buyers of {source_sku} "
                f"also purchased {best['sku']} ({product.name}). "
                f"Price: ₹{product.price_paise / 100:,.2f}"
            ),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        self.db.add(recommendation)
        await self.db.flush()

        logger.info("Upsell recommendation generated",
                     source=source_sku, recommended=best["sku"],
                     probability=best["probability"])

        return recommendation

    async def get_upsell(self, order_id: str) -> UpsellRecommendation | None:
        """Get upsell recommendation for an order."""
        stmt = (
            select(UpsellRecommendation)
            .where(UpsellRecommendation.source_order_id == order_id)
            .order_by(UpsellRecommendation.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def accept_upsell(self, upsell_id: str) -> bool:
        stmt = select(UpsellRecommendation).where(UpsellRecommendation.id == upsell_id)
        result = await self.db.execute(stmt)
        upsell = result.scalar_one_or_none()
        if upsell and upsell.status == UpsellStatus.PROPOSED.value:
            upsell.status = UpsellStatus.ACCEPTED.value
            return True
        return False

    async def reject_upsell(self, upsell_id: str) -> bool:
        stmt = select(UpsellRecommendation).where(UpsellRecommendation.id == upsell_id)
        result = await self.db.execute(stmt)
        upsell = result.scalar_one_or_none()
        if upsell and upsell.status == UpsellStatus.PROPOSED.value:
            upsell.status = UpsellStatus.REJECTED.value
            return True
        return False

    async def _get_product(self, sku: str) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

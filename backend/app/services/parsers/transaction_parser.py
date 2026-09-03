"""Financial transaction tabular parser with graph anomaly pattern detection."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

class TransactionParser:
    """Dynamic CSV/tabular parser for bank transactions with pattern detection."""

    FROM_ALIASES = {"from", "from_account", "debitor", "payer", "sender", "source_account", "remitter"}
    TO_ALIASES = {"to", "to_account", "creditor", "beneficiary", "receiver", "target_account", "payee"}
    AMOUNT_ALIASES = {"amount", "amt", "transfer_amount", "txn_amount", "value", "sum"}
    DATE_ALIASES = {"date", "txn_date", "transaction_date", "timestamp", "datetime"}
    TYPE_ALIASES = {"type", "transaction_type", "channel", "mode", "txn_type"}
    REMARKS_ALIASES = {"remarks", "narration", "description", "note"}

    def _match_col(self, header: str, aliases: set[str]) -> bool:
        clean = re.sub(r"[^a-z0-9]", "", header.lower())
        return any(clean == re.sub(r"[^a-z0-9]", "", a) or a in clean for a in aliases)

    def parse(self, content: str) -> dict[str, Any]:
        reader = csv.reader(io.StringIO(content.strip()))
        rows = list(reader)
        if not rows:
            return {"entities": [], "relationships": [], "patterns_detected": []}

        headers = [h.strip() for h in rows[0]]
        from_idx = None
        to_idx = None
        amount_idx = None
        date_idx = None
        type_idx = None
        remarks_idx = None

        for idx, h in enumerate(headers):
            if from_idx is None and self._match_col(h, self.FROM_ALIASES):
                from_idx = idx
            elif to_idx is None and self._match_col(h, self.TO_ALIASES):
                to_idx = idx
            elif amount_idx is None and self._match_col(h, self.AMOUNT_ALIASES):
                amount_idx = idx
            elif date_idx is None and self._match_col(h, self.DATE_ALIASES):
                date_idx = idx
            elif type_idx is None and self._match_col(h, self.TYPE_ALIASES):
                type_idx = idx
            elif remarks_idx is None and self._match_col(h, self.REMARKS_ALIASES):
                remarks_idx = idx

        # Fallbacks
        if from_idx is None or to_idx is None:
            if len(headers) >= 3:
                from_idx = 1
                to_idx = 2
                amount_idx = 3 if len(headers) > 3 else None

        unique_entities: dict[str, str] = {}  # name -> entity_type
        transactions: list[dict[str, Any]] = []

        for row in rows[1:]:
            if not row or len(row) <= max(from_idx or 0, to_idx or 0):
                continue

            src = row[from_idx].strip()
            tgt = row[to_idx].strip()
            if not src or not tgt:
                continue

            src_type = "BankAccount" if src.upper().startswith("ACC") or src.isdigit() else "Person"
            tgt_type = "BankAccount" if tgt.upper().startswith("ACC") or tgt.isdigit() else "Person"

            unique_entities[src] = src_type
            unique_entities[tgt] = tgt_type

            amt = 0.0
            if amount_idx is not None and len(row) > amount_idx:
                raw_amt = re.sub(r"[^\d.]", "", row[amount_idx])
                try:
                    amt = float(raw_amt) if raw_amt else 0.0
                except ValueError:
                    amt = 0.0

            dt = row[date_idx].strip() if date_idx is not None and len(row) > date_idx else None
            m_type = row[type_idx].strip() if type_idx is not None and len(row) > type_idx else "TRANSFER"
            remarks = row[remarks_idx].strip() if remarks_idx is not None and len(row) > remarks_idx else ""

            transactions.append({
                "from": src,
                "from_type": src_type,
                "to": tgt,
                "to_type": tgt_type,
                "amount": amt,
                "date": dt,
                "type": m_type,
                "remarks": remarks,
            })

        # Pattern detection:
        patterns: list[dict[str, Any]] = []

        # 1. Circular transactions: A -> B -> C -> A
        graph_edges: dict[str, list[str]] = {}
        for tx in transactions:
            graph_edges.setdefault(tx["from"], []).append(tx["to"])

        circular_chains: list[list[str]] = []
        for start in graph_edges:
            for hop1 in graph_edges.get(start, []):
                for hop2 in graph_edges.get(hop1, []):
                    if start in graph_edges.get(hop2, []):
                        chain = [start, hop1, hop2, start]
                        if not any(set(chain) == set(c) for c in circular_chains):
                            circular_chains.append(chain)

        for c in circular_chains:
            patterns.append({
                "pattern_type": "CIRCULAR_FLOW",
                "severity": "HIGH",
                "description": f"Potential circular financial loop detected: {' → '.join(c)}",
                "entities_involved": list(set(c)),
                "recommended_action": "Subpoena complete banking audit logs for layering verification.",
            })

        # 2. Round amounts
        round_txs = [tx for tx in transactions if tx["amount"] > 0 and tx["amount"] % 5000 == 0]
        if len(round_txs) >= 2:
            patterns.append({
                "pattern_type": "ROUND_VALUE_TRANSFERS",
                "severity": "MEDIUM",
                "description": f"{len(round_txs)} transactions feature suspicious round numbers (multiples of ₹5,000).",
                "entities_involved": list({tx["from"] for tx in round_txs} | {tx["to"] for tx in round_txs}),
                "recommended_action": "Verify invoicing or stated transaction purpose.",
            })

        # Build Entity objects
        entities = [
            {
                "entity_type": e_type,
                "value": e_val,
                "normalized_value": e_val,
                "confidence": 0.94,
                "extraction_method": "RULE_BASED",
                "source_text": e_val,
                "requires_verification": False,
            }
            for e_val, e_type in unique_entities.items()
        ]

        # Build Relationships
        relationships = [
            {
                "source_value": tx["from"],
                "source_type": tx["from_type"],
                "relationship_type": "TRANSFERRED_MONEY_TO",
                "target_value": tx["to"],
                "target_type": tx["to_type"],
                "confidence": 0.92,
                "amount": tx["amount"],
                "relationship_origin": "OBSERVED",
                "explanation": f"Financial transfer of ₹{tx['amount']:,.2f} via {tx['type']}{' (' + tx['remarks'] + ')' if tx['remarks'] else ''}",
                "evidence_text": f"Txn amount: ₹{tx['amount']}, Mode: {tx['type']}",
                "timestamp": tx["date"],
                "requires_verification": False,
            }
            for tx in transactions
        ]

        return {
            "document_type": "FINANCIAL_TRANSACTIONS",
            "total_transactions": len(transactions),
            "entities": entities,
            "relationships": relationships,
            "patterns_detected": patterns,
        }

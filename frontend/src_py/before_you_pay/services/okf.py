"""Open Knowledge Format (OKF) catalog service loading rules from standard JSON."""

import json
from pathlib import Path

from before_you_pay.models import OkfCategory, OkfQuery, OkfRuleEvidence


class OkfCatalogService:
    """Loads and queries versioned, curated rules from the Open Knowledge Format JSON catalog."""

    def __init__(self, catalog_path: str = "./data/okf") -> None:
        raw_p = Path(catalog_path)
        if raw_p.exists() and list(raw_p.glob("*.json")):
            self.catalog_path = raw_p
        else:
            # Fallback search locations
            candidates = [
                Path(__file__).resolve().parents[3] / "data" / "okf",
                Path.cwd() / "data" / "okf",
                Path.cwd() / "frontend" / "data" / "okf",
                raw_p,
            ]
            self.catalog_path = next((c for c in candidates if c.exists() and list(c.glob("*.json"))), raw_p)
        self._rules: dict[str, OkfRuleEvidence] = {}
        self._file_mtimes: dict[str, float] = {}
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Parse all JSON rule catalogs in the designated directory."""
        if not self.catalog_path.exists():
            try:
                self.catalog_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return

        json_files = list(self.catalog_path.glob("*.json"))
        new_rules: dict[str, OkfRuleEvidence] = {}
        new_mtimes: dict[str, float] = {}

        for file_path in json_files:
            try:
                new_mtimes[str(file_path)] = file_path.stat().st_mtime
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if not data or "rules" not in data:
                        continue

                    for item in data["rules"]:
                        rule = OkfRuleEvidence(
                            rule_id=item["rule_id"],
                            rule_name=item["rule_name"],
                            category=OkfCategory(item["category"]),
                            summary=item["summary"],
                            source_reference=item["source_reference"],
                            version=item.get("version", "1.0.0"),
                            guidance=item["guidance"],
                        )
                        new_rules[rule.rule_id] = rule
            except Exception as e:
                print(f"Warning: Failed to load OKF catalog file {file_path}: {e}")

        self._rules = new_rules
        self._file_mtimes = new_mtimes

    def _check_and_reload(self) -> None:
        """Check if any catalog file has been modified or added and reload immediately."""
        if not self.catalog_path.exists():
            return
        json_files = list(self.catalog_path.glob("*.json"))
        current_mtimes = {str(fp): fp.stat().st_mtime for fp in json_files}
        if current_mtimes != self._file_mtimes:
            self._load_catalog()

    async def query_rules(self, query: OkfQuery) -> list[OkfRuleEvidence]:
        """Query curated rules matching categories and keywords, refreshing if files updated."""
        self._check_and_reload()
        results: list[OkfRuleEvidence] = []
        filter_categories = set(query.categories) if query.categories else None
        keywords = [kw.lower() for kw in query.concept_keywords]

        for rule in self._rules.values():
            if filter_categories and rule.category not in filter_categories:
                continue

            if keywords:
                text_to_search = f"{rule.rule_name} {rule.summary} {rule.guidance}".lower()
                if not any(kw in text_to_search for kw in keywords):
                    continue

            results.append(rule)

        return results

    async def get_rule_by_id(self, rule_id: str) -> OkfRuleEvidence | None:
        """Retrieve a specific OKF rule by canonical ID, refreshing if files updated."""
        self._check_and_reload()
        return self._rules.get(rule_id)

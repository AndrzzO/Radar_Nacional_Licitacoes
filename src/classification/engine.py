"""Classificação determinística por expressões inteiras e contexto local."""
import re
import unicodedata
from collections import defaultdict

ENGINE_VERSION = "1.0"
DEFAULT_SETTINGS = {"minimum": 4, "medium": 7, "high": 12, "margin": 2, "context_window": 12}


def normalize(text):
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c))))


class Classifier:
    def __init__(self, catalog):
        self.catalog = catalog
        self.settings = {**DEFAULT_SETTINGS, **catalog.get("settings", {})}
        self.categories = {c["id"]: c for c in catalog["categories"] if c["active"]}
        self.subcategories = {s["id"]: s for s in catalog["subcategories"] if s["active"] and s["category_id"] in self.categories}
        self.rules = []
        for rule in catalog["rules"]:
            if not rule["active"] or rule["subcategory_id"] not in self.subcategories:
                continue
            terms = [rule["expression"], *rule.get("synonyms", [])]
            patterns = [re.compile(r"(?<!\w)" + re.escape(normalize(t)) + r"(?!\w)") for t in terms]
            self.rules.append((rule, patterns))

    def classify(self, text):
        normalized = normalize(text)
        tokens = list(re.finditer(r"\S+", normalized))
        matches, exclusions = [], []
        for rule, patterns in self.rules:
            for pattern in patterns:
                for match in pattern.finditer(normalized):
                    center = next((i for i, t in enumerate(tokens) if t.end() > match.start()), 0)
                    end_token = next((i for i, t in enumerate(tokens) if t.end() >= match.end()), center)
                    w = self.settings["context_window"]
                    near = " ".join(t.group() for t in tokens[max(0, center-w):end_token+w+1])
                    contexts = rule.get("context", [])
                    if contexts and not any(re.search(r"(?<!\w)"+re.escape(normalize(t))+r"(?!\w)", near) for t in contexts):
                        continue
                    evidence = {"rule_id": rule["id"], "expression": rule["expression"], "matched": match.group(), "start": match.start(), "end": match.end(), "weight": rule["weight"], "subcategory_id": rule["subcategory_id"], "kind": rule["kind"]}
                    (exclusions if rule["kind"] == "exclusion" else matches).append(evidence)
        accepted, suppressed = [], []
        used_rules = set()
        # Mais específica primeiro; contexto precede peso em empates de tamanho.
        matches.sort(key=lambda m: (-(m["end"]-m["start"]), -(m["kind"] == "contextual"), -m["weight"], m["rule_id"]))
        for m in matches:
            blockers = [e for e in exclusions if e["subcategory_id"] == m["subcategory_id"] and m["start"] < e["end"] and e["start"] < m["end"]]
            if blockers:
                suppressed.append({**m, "reason": "Exclusão no mesmo trecho", "exclusion_rules": [e["rule_id"] for e in blockers]})
                continue
            if m["rule_id"] in used_rules:
                continue
            if any(m["start"] < a["end"] and a["start"] < m["end"] for a in accepted):
                suppressed.append({**m, "reason": "Expressão mais específica sobreposta"})
                continue
            accepted.append(m)
            used_rules.add(m["rule_id"])
        scores = defaultdict(int)
        for m in accepted:
            scores[m["subcategory_id"]] += m["weight"]
        groups = defaultdict(list)
        for sid, score in scores.items():
            if score >= self.settings["minimum"]:
                sub = self.subcategories[sid]
                groups[sub["category_id"]].append((sid, score))
        candidates = []
        for cid, subs in groups.items():
            subs.sort(key=lambda x: (-x[1], x[0]))
            sub_conflict = len(subs) > 1 and subs[0][1]-subs[1][1] < self.settings["margin"]
            sid = None if sub_conflict else subs[0][0]
            score = sum(s for _, s in subs)
            confidence = "Alta" if score >= self.settings["high"] and not sub_conflict else "Média" if score >= self.settings["medium"] else "Baixa"
            candidates.append({"category_id": cid, "category": self.categories[cid]["name"], "subcategory_id": sid, "subcategory": self.subcategories[sid]["name"] if sid else "Revisar subcategoria", "score": score, "confidence": confidence, "primary": False, "evidence": [m for m in accepted if self.subcategories[m["subcategory_id"]]["category_id"] == cid]})
        candidates.sort(key=lambda c: (-c["score"], -self.categories[c["category_id"]].get("priority", 0), c["category_id"]))
        conflict = len(candidates)>1 and candidates[0]["score"]-candidates[1]["score"] < self.settings["margin"]
        if candidates and not conflict:
            candidates[0]["primary"] = True
        reason = "Conflito entre categorias: revisar" if conflict else "Evidência insuficiente" if not candidates else "Expressões específicas e contexto; pontos consolidados por categoria"
        return {"primary": next((c for c in candidates if c["primary"]), None), "classifications": candidates, "reason": reason, "exclusions": exclusions, "suppressed": suppressed, "normalized": normalized, "engine_version": ENGINE_VERSION}

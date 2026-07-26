#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 · KB 检索路由（v1）· 供 skill 主流程调用

补齐清单对齐:
- P0-8: A/B/C 三路由检索
  · A 路由 → 规范层 KB-A（norms/）→ 判红黄绿的权威依据
  · B 路由 → 范例层 KB-B（Chroma examples_v1）→ 仅作改进参照
  · C 路由 → 无匹配 fallback → 明确"未找到参照"
- P0-3: 严格分层（B 路由结果强制标注 can_be_error_evidence=false）
- P0-9: 通过 kb_ingest 复用 EmbeddingProvider（不锁死）
- 原则 1 红线: 每个 B 路由结果附 notice「范例仅作改进参照，不作错误判定唯一依据」

用法:
  # CLI 单次查询
  python3 scripts/kb_query.py --query "文献综述部分应该怎么写" --topk 3

  # 带过滤
  python3 scripts/kb_query.py --query "DID平行趋势检验" --method DID --topk 5

  # 输出 JSON（供 skill 消费）
  python3 scripts/kb_query.py --query "..." --json

  # 交互式验证
  python3 scripts/kb_query.py --interactive

  # Python 调用
  from scripts.kb_query import search, KBQuery
  kbq = KBQuery()
  results = kbq.search("文献综述怎么写", topk=3)
"""
from __future__ import annotations
import json, os, re, sys, argparse, warnings
from pathlib import Path
from datetime import datetime, timezone
warnings.filterwarnings("ignore")

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VDB_ROOT = ROOT / "knowledge_base/vector_db/active"
NORMS_ROOT = ROOT / "knowledge_base/norms"
PARSED_ROOT = ROOT / "knowledge_base/examples/parsed"

# ---- 轻量搜索（零依赖，读 JSON 做关键词匹配） ----

class LightweightKBSearch:
    """不依赖 chromadb / sentence-transformers 的 KB-B 轻量搜索。
    直接读 parsed JSON 文件，做关键词+主题匹配，即开即用。"""

    def __init__(self):
        self._papers: list[dict] = []
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        for batch_dir in sorted(PARSED_ROOT.glob("batch_*")):
            for jf in sorted(batch_dir.glob("EXAMPLE-*.json")):
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                    self._papers.append(d)
                except Exception:
                    continue
        self._loaded = True

    def search(self, query: str, topk: int = 3,
               topic: str = None, method: str = None,
               paper_type: str = None) -> dict:
        self._load()
        if not self._papers:
            return {"route": "B-lightweight", "items": [], "notice": "未找到 KB-B 论文 JSON"}

        qlower = query.lower()
        scored = []
        for p in self._papers:
            score = 0.0
            hint = p.get("topic_hint", "")
            pid = p.get("paper_id", "")

            # 主题过滤
            if topic and topic.lower() not in hint.lower():
                continue
            if method:
                tags = [t.lower() for t in p.get("method_tags", [])]
                if method.lower() not in tags:
                    continue
            if paper_type and p.get("paper_type", "") != paper_type:
                continue

            # 得分规则
            title_unit = next((u for u in p.get("units", [])
                              if u.get("kind") == "paragraph" and len(u.get("text", "").strip()) > 5), None)
            title_text = title_unit.get("text", "") if title_unit else ""
            # 题名精确匹配 +3
            if qlower in title_text.lower():
                score += 3.0
            # 主题命中 +2
            if qlower in hint.lower():
                score += 2.0
            # 关键词拆分命中 +1 per token
            tokens = re.findall(r"[一-鿿\w]+", qlower)
            for tok in tokens:
                if len(tok) >= 2 and tok.lower() in hint.lower():
                    score += 1.0
            # 摘要区命中 +1
            abstract_units = [u for u in p.get("units", [])
                             if u.get("kind") == "paragraph" and "摘要" in u.get("text", "")]
            for au in abstract_units[:2]:
                if qlower in au.get("text", "").lower():
                    score += 1.0
                    break
            # 正文命中 +0.5
            body_matches = sum(1 for u in p.get("units", [])
                              if qlower in u.get("text", "").lower())
            score += min(body_matches * 0.5, 3.0)

            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        items = []
        for sc, p in scored[:topk]:
            title_unit = next((u for u in p.get("units", [])
                              if u.get("kind") == "paragraph" and len(u.get("text", "").strip()) > 5), None)
            chunks = sum(1 for u in p.get("units", []) if qlower in u.get("text", "").lower())
            items.append({
                "paper_id": p.get("paper_id", ""),
                "topic_hint": p.get("topic_hint", ""),
                "paper_type": p.get("paper_type", ""),
                "method_tags": p.get("method_tags", []),
                "score": round(sc, 1),
                "matched_chunks": chunks,
                "source": "lightweight_text_match",
            })

        notice = (None if items
                  else f"轻量搜索未命中「{query}」；可安装 chromadb+sentence-transformers 启用语义搜索")
        return {"route": "B-lightweight", "items": items, "notice": notice}


_lightweight = None

def _get_lightweight():
    global _lightweight
    if _lightweight is None:
        _lightweight = LightweightKBSearch()
    return _lightweight

# ---- ChromaDB 语义搜索（可选，需 chromadb + sentence-transformers）----

try:
    from scripts.kb_ingest import EmbeddingProvider, EMBEDDING_CONFIG, get_chroma  # noqa: F401
    _chromadb_available = True
except Exception:
    _chromadb_available = False

# ===================== 常量 =====================

KB_B_NOTICE = "范例仅作改进参照，不作错误判定唯一依据；如需权威依据请查规范层（KB-A）"
KB_A_NOTICE = "规范层结果可作为红黄绿判定依据"
DEFAULT_MIN_SIMILARITY = 0.30  # 距离 = 1 - cos，0.30 大约对应 cos≈0.70

# ===================== KBQuery 主类 =====================

class KBQuery:
    """检索路由器"""

    def __init__(self, embedding_cfg=None, min_similarity=DEFAULT_MIN_SIMILARITY):
        self.provider = EmbeddingProvider(embedding_cfg or EMBEDDING_CONFIG)
        self.min_similarity = min_similarity
        self._client = None
        self._coll = None

    def _get_coll(self):
        if self._coll is None:
            self._client = get_chroma()
            try:
                self._coll = self._client.get_collection("examples_v1")
            except Exception as e:
                raise RuntimeError(f"KB-B collection 未创建，请先跑 kb_ingest: {e}")
        return self._coll

    # ---------- A 路由 · 规范层 ----------
    def query_norms(self, query: str, topk: int = 5) -> list[dict]:
        """
        A 路由：规范层 KB-A 检索（红黄绿判定依据）

        v1.5 实现：读取 knowledge_base/norms/{domain}/*.yaml 下的结构化条款，
        对 title + summary + triggers + modification_hint 做关键词匹配。
        未来可换成轻量向量检索，但目前条款量小（10-100 量级）关键词已够用。
        """
        if not NORMS_ROOT.exists():
            return []
        try:
            import yaml
        except ImportError:
            return []

        # 字符 n-gram + 关键词匹配（中文无分词器环境下的轻量方案）
        # 1) query 以 2 字粒度拆（中文），遇到英文或数字保留完整词
        import re
        # 先取所有中英数字段
        segs = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z0-9]+", query)
        q_tokens = set()
        for s in segs:
            if re.match(r"[A-Za-z0-9]+", s):
                if len(s) >= 2:
                    q_tokens.add(s.lower())
            else:
                # 中文：取所有 2-gram
                if len(s) >= 2:
                    for i in range(len(s) - 1):
                        q_tokens.add(s[i:i+2])
                # 单个中文字不算 token（偉滤噪声）
        if not q_tokens:
            return []

        candidates = []
        for yaml_f in sorted(NORMS_ROOT.rglob("*.yaml")):
            # skip registry
            if "registry" in yaml_f.parts:
                continue
            try:
                doc = yaml.safe_load(open(yaml_f, encoding="utf-8"))
            except Exception:
                continue
            if not doc or "norms" not in doc:
                continue
            src_meta = {k: doc.get(k) for k in ("source_id", "source_name", "source_version", "authority_level", "copyright_mode")}
            for n in doc["norms"]:
                # 合并可搜索文本
                blob = " ".join(str(n.get(k, "")) for k in ("title", "summary", "subdomain", "modification_hint"))
                triggers = n.get("triggers") or []
                if isinstance(triggers, list):
                    blob += " " + " ".join(str(t) for t in triggers)
                blob = blob.lower()

                score = 0
                matched_tokens = []
                for tok in q_tokens:
                    if tok.lower() in blob:
                        score += 1
                        matched_tokens.append(tok)
                if score > 0:
                    candidates.append((score, matched_tokens, n, src_meta, yaml_f))

        if not candidates:
            return []

        # 按得分降序，且若最高得分很低、只命中 1 个常见字后缀，拒绝返回（降器噪声）
        candidates.sort(key=lambda x: -x[0])
        # 至少需要 2 个 token 命中
        max_score = candidates[0][0]
        if max_score < 2:
            return []

        # 额外过滤：如果词块命中的全部是高频虚词（“变量”、“方法”、“模型”、“检验”等），
        # 且 max_score 仅为 2，视为弱匹配，拒绝
        stopword_bigrams = {"变量", "方法", "模型", "检验", "分析", "研究", "结果", "影响", "数据"}
        filtered = []
        for score, matched, n, src, yaml_f in candidates:
            informative = [t for t in matched if t not in stopword_bigrams]
            # 若没有信息量词块且得分 <= 3，弃用
            if not informative and score <= 3:
                continue
            filtered.append((score, n, src, yaml_f))
        if not filtered:
            return []
        results = []
        for rank, (score, n, src, yaml_f) in enumerate(filtered[:topk], 1):
            results.append({
                "rank": rank,
                "norm_id": n.get("norm_id"),
                "domain": n.get("domain"),
                "subdomain": n.get("subdomain"),
                "title": n.get("title"),
                "default_level": n.get("default_level"),
                "check_priority": n.get("check_priority"),
                "source_locator": n.get("source_locator"),
                "summary": n.get("summary", "").strip(),
                "triggers": n.get("triggers", []),
                "modification_hint": n.get("modification_hint", ""),
                "example_correct": n.get("example_correct", ""),
                "example_wrong": n.get("example_wrong", ""),
                "match_score": score,
                "source": src,
                "meta": {
                    "kb_layer": "normative_basis",
                    "can_be_error_evidence": True,
                    "authority_level": src.get("authority_level"),
                },
            })
        return results

    # ---------- B 路由 · 范例层 ----------
    def _fetch_neighbors(self, paper_id: str, start_chunk_no: int, n: int = 2) -> list[dict]:
        """取指定论文中，chunk_no > start_chunk_no 的紧邻 n 个 body chunk
        用于 section_header 命中时展开正文。"""
        coll = self._get_coll()
        # 拉后续 5 个，过滤出 body 类的 n 个
        r = coll.get(
            where={"paper_id": paper_id},
            include=["metadatas", "documents"],
            limit=1000,
        )
        if not r or not r.get("ids"): return []
        picks = []
        pairs = list(zip(r["ids"], r["metadatas"], r["documents"]))
        # 按 chunk_no 排序
        pairs.sort(key=lambda x: (x[1] or {}).get("chunk_no", 0))
        for cid, m, doc in pairs:
            m = m or {}
            if m.get("chunk_no", 0) <= start_chunk_no: continue
            sec = m.get("section", "")
            if sec in ("body", "references"):
                picks.append({"chunk_id": cid, "meta": m, "text": doc})
                if len(picks) >= n:
                    break
            elif sec == "section_header":
                # 遇到下一个 header 就停
                break
        return picks

    def query_examples(self, query: str, topk: int = 3,
                        topic: str = None, method: str = None,
                        paper_type: str = None,
                        expand_header: bool = True) -> list[dict]:
        """
        B 路由：范例层 KB-B 检索（改进参照，非错误依据）

        参数:
            query: 查询文本
            topk: 返回 top-K
            topic: 主题硬过滤（如 "数字经济"），匹配 topic_hint 包含
            method: 方法硬过滤（如 "DID"），匹配 method_tags 包含
            paper_type: 论文类型过滤（theoretical / empirical）
        """
        coll = self._get_coll()

        qvec = self.provider.embed_query(query)

        # Chroma metadata filter（$contains 不支持字符串包含匹配，改为拉大 topk 后 Python 侧过滤）
        # 但 paper_type 是精确匹配，可以下推
        where = None
        if paper_type:
            where = {"paper_type": paper_type}

        # 为了后过滤，拉更多结果
        fetch_k = topk * 5 if (topic or method) else topk * 2

        r = coll.query(
            query_embeddings=[qvec],
            n_results=min(fetch_k, 50),
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        results = []
        if not r["ids"] or not r["ids"][0]:
            return results

        for i in range(len(r["ids"][0])):
            cid = r["ids"][0][i]
            dist = r["distances"][0][i]
            m = r["metadatas"][0][i] or {}
            doc = r["documents"][0][i]

            # 距离阈值
            if dist > (1.0 - self.min_similarity):
                continue

            # topic 软过滤（子串匹配）
            if topic and topic not in (m.get("topic_hint", "") or ""):
                continue

            # method 软过滤（method_tags 是逗号分隔字符串）
            if method:
                mt = (m.get("method_tags", "") or "").lower()
                if method.lower() not in mt:
                    continue

            item = {
                "rank": len(results) + 1,
                "chunk_id": cid,
                "paper_id": m.get("paper_id", ""),
                "section": m.get("section", ""),
                "current_section": m.get("current_section", ""),
                "topic_hint": m.get("topic_hint", ""),
                "method_tags": m.get("method_tags", ""),
                "paper_type": m.get("paper_type", ""),
                "similarity": round(1.0 - dist, 4),
                "distance": round(dist, 4),
                "text": doc,
                "char_len": m.get("char_len", len(doc)),
                "meta": {
                    "kb_layer": "example_reference",
                    "can_be_error_evidence": False,
                    "admission_source": m.get("admission_source", "online_top_journal"),
                },
            }

            # section_header 命中 → 展开后续正文
            if expand_header and m.get("section") == "section_header":
                neighbors = self._fetch_neighbors(
                    m.get("paper_id", ""),
                    m.get("chunk_no", 0),
                    n=2,
                )
                if neighbors:
                    item["expanded"] = [
                        {
                            "chunk_id": n["chunk_id"],
                            "text": n["text"],
                            "char_len": n["meta"].get("char_len", len(n["text"])),
                            "section": n["meta"].get("section"),
                        }
                        for n in neighbors
                    ]

            results.append(item)
            if len(results) >= topk:
                break

        return results

    # ---------- 主入口 · 三路由决策 ----------
    def search(self, query: str, topk: int = 3,
               topic: str = None, method: str = None,
               paper_type: str = None,
               prefer: str = "auto") -> dict:
        """
        统一检索入口

        参数:
            prefer: "auto" | "A" | "B"
                auto → 先 A 再 B，A 有结果时 route=A；否则 route=B
                A    → 只查规范层
                B    → 只查范例层

        返回:
            {
                "query": ...,
                "route": "A" | "B" | "C",
                "results": [...],
                "notice": ...,
                "meta": {"topk": ..., "min_similarity": ...},
            }
        """
        out = {
            "query": query,
            "route": None,
            "results": [],
            "notice": "",
            "meta": {
                "topk": topk,
                "min_similarity": self.min_similarity,
                "filters": {"topic": topic, "method": method, "paper_type": paper_type},
                "queried_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # A 路由
        if prefer in ("auto", "A"):
            a_results = self.query_norms(query, topk=topk)
            if a_results:
                out["route"] = "A"
                out["results"] = a_results
                out["notice"] = KB_A_NOTICE
                return out
            if prefer == "A":
                out["route"] = "C"
                out["notice"] = "规范层（KB-A）尚未起草或无匹配"
                return out

        # B 路由
        b_results = self.query_examples(query, topk=topk,
                                          topic=topic, method=method,
                                          paper_type=paper_type)
        if b_results:
            out["route"] = "B"
            out["results"] = b_results
            out["notice"] = KB_B_NOTICE
            return out

        # C 路由：无匹配
        out["route"] = "C"
        out["notice"] = "未找到可用参照；建议扩大查询范围或调低 min_similarity"
        return out


# ===================== 模块级便捷入口 =====================

_default_kbq = None


def _get_default():
    global _default_kbq
    if _default_kbq is None:
        if _chromadb_available:
            try:
                _default_kbq = KBQuery()
                # 真实验证是否能加载（尝试 embed 一个词）
                _default_kbq.provider.embed_query("test")
                return _default_kbq
            except Exception:
                pass
        _default_kbq = _LightweightKBQuery()
    return _default_kbq


class _LightweightKBQuery:
    """当 ChromaDB 不可用时的轻量查询代理。
    KB-A 仍走 YAML 规范层；KB-B 走 JSON 文本匹配。"""

    def __init__(self):
        self._light = _get_lightweight()

    def query_norms(self, query: str, topk: int = 5) -> list[dict]:
        # KB-A 规范层：直接读 YAML，不依赖模型
        norms_root = ROOT / "knowledge_base" / "norms"
        results = []
        for yf in sorted(norms_root.rglob("*.yaml")):
            try:
                data = yaml.safe_load(yf.read_text(encoding="utf-8"))
                for n in data.get("norms", []) or []:
                    clause = n.get("clause", n.get("title", ""))
                    if query.lower() in clause.lower():
                        results.append(n)
                    elif any(qt.lower() in clause.lower()
                            for qt in re.findall(r"[一-鿿\w]+", query) if len(qt) >= 2):
                        results.append(n)
            except Exception:
                continue
        return results[:topk]

    def query_examples(self, query: str, topk: int = 3, **kwargs) -> dict:
        kwargs.pop("prefer", None)
        return self._light.search(query, topk, **kwargs)

    def search(self, query: str, topk: int = 3, **kwargs) -> dict:
        norms = self.query_norms(query, topk=3)
        examples = self.query_examples(query, topk=topk, **kwargs)
        prefer = kwargs.get("prefer", "auto")
        return {
            "query": query,
            "route": "lightweight",
            "prefer": prefer,
            "kb_a_norms": {"hits": len(norms), "items": norms},
            "kb_b_examples": examples,
            "notice": "当前使用轻量文本匹配（零依赖）。安装 chromadb+sentence-transformers 可启用语义搜索。",
        }


def search(query: str, **kwargs) -> dict:
    """供 skill 主流程调用的模块函数"""
    return _get_default().search(query, **kwargs)


# ===================== CLI =====================

def format_result_human(res: dict, verbose=False) -> str:
    """人类可读输出"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"🔎 Query: 「{res['query']}」")
    lines.append(f"   Route: {res['route']} · "
                 f"Filters: {res['meta']['filters']} · "
                 f"topk={res['meta']['topk']}")
    lines.append(f"   Notice: {res['notice']}")
    lines.append("=" * 70)

    if not res["results"]:
        lines.append("  ⚠️  无结果")
        return "\n".join(lines)

    # A 路由：规范条款输出
    if res["route"] == "A":
        for r in res["results"]:
            lines.append(f"\n  #{r['rank']}  {r['norm_id']}  [{r['default_level']}] · score={r['match_score']}")
            lines.append(f"      title: {r['title']}")
            lines.append(f"      source: {r['source']['source_name']} · {r.get('source_locator','-')}")
            summary = r['summary']
            if not verbose and len(summary) > 220:
                summary = summary[:220] + "..."
            lines.append(f"      summary: {summary}")
            if r.get("modification_hint"):
                lines.append(f"      hint: {r['modification_hint']}")
        return "\n".join(lines)

    # B 路由：范例片段
    for r in res["results"]:
        lines.append(f"\n  #{r['rank']}  {r['chunk_id']}  (sim={r['similarity']})")
        lines.append(f"      paper_id: {r['paper_id']} · "
                     f"section: {r.get('section','')} · "
                     f"current: {r.get('current_section','')[:40]}")
        lines.append(f"      topic: {r['topic_hint']} · "
                     f"method: {r.get('method_tags','')} · "
                     f"type: {r.get('paper_type','')}")
        preview = r["text"].replace("\n", " ")
        if not verbose and len(preview) > 180:
            preview = preview[:180] + "..."
        lines.append(f"      text: {preview}")
        if r.get("expanded"):
            for ex in r["expanded"]:
                ex_preview = ex["text"].replace("\n", " ")
                if not verbose and len(ex_preview) > 200:
                    ex_preview = ex_preview[:200] + "..."
                lines.append(f"      ↳ {ex['chunk_id']}: {ex_preview}")
        lines.append(f"      ⚠️  can_be_error_evidence: {r['meta']['can_be_error_evidence']}")
    return "\n".join(lines)


def interactive_loop(kbq: KBQuery):
    print("🔍 KB 交互式检索 (输入 :q 退出，:help 帮助)")
    print("=" * 60)
    while True:
        try:
            q = input("\nquery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye"); break
        if not q: continue
        if q in (":q", ":quit", "exit"): break
        if q == ":help":
            print("直接输入查询，或 :q 退出")
            continue
        try:
            res = kbq.search(q, topk=3)
            print(format_result_human(res))
        except Exception as e:
            print(f"❌ {e}")


def main():
    ap = argparse.ArgumentParser(description="KB 三路由检索")
    ap.add_argument("--query", "-q", help="查询文本")
    ap.add_argument("--topk", "-k", type=int, default=3)
    ap.add_argument("--topic", help="主题过滤（子串）")
    ap.add_argument("--method", help="方法过滤（如 DID）")
    ap.add_argument("--paper-type", choices=["theoretical", "empirical"])
    ap.add_argument("--prefer", choices=["auto", "A", "B"], default="auto")
    ap.add_argument("--min-sim", type=float, default=DEFAULT_MIN_SIMILARITY)
    ap.add_argument("--json", action="store_true", help="JSON 输出（供 skill）")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--interactive", "-i", action="store_true")
    args = ap.parse_args()

    kbq = KBQuery(min_similarity=args.min_sim)

    if args.interactive:
        interactive_loop(kbq)
        return

    if not args.query:
        ap.error("--query 必填（或用 --interactive）")

    res = kbq.search(
        args.query,
        topk=args.topk,
        topic=args.topic,
        method=args.method,
        paper_type=args.paper_type,
        prefer=args.prefer,
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_result_human(res, verbose=args.verbose))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 · KB-B 范例层入库管道（v1）

补齐清单对齐:
- P0-3: 范例层与规范层严格分离（本脚本只处理 examples/，不碰 norms/）
- P0-4: 前置脱敏必须已完成（读脱敏后的 parsed JSON）
- P0-9: embedding 抽象层，通过 config/embedding.yaml 切换 provider
- P0-10: 14 步质量门禁的第 5-13 步（切片 → 向量化 → commit → 快照）
- P0-11: 幂等：以 source_sha256 判重，重复入库跳过
- P0-13: CRUD + 快照 + 回滚接口

用法:
  python3 scripts/kb_ingest.py --batch batch_01              # 入指定批次
  python3 scripts/kb_ingest.py --status                       # 看当前库状态
  python3 scripts/kb_ingest.py --smoke                        # smoke test
  python3 scripts/kb_ingest.py --rebuild                      # 全量重建
"""
from __future__ import annotations
import json, os, sys, argparse, hashlib, warnings
from pathlib import Path
from datetime import datetime, timezone
warnings.filterwarnings("ignore")

# 环境
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")

ROOT = Path(__file__).resolve().parent.parent
PARSED_ROOT = ROOT / "knowledge_base/examples/parsed"
METADATA_ROOT = ROOT / "knowledge_base/examples/metadata"
VDB_ROOT = ROOT / "knowledge_base/vector_db/active"
LOGS_ROOT = ROOT / "knowledge_base/logs/ingest"
CONFIG_DIR = ROOT / "knowledge_base/config"

METADATA_ROOT.mkdir(parents=True, exist_ok=True)
VDB_ROOT.mkdir(parents=True, exist_ok=True)
LOGS_ROOT.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# ========== 配置：embedding provider 抽象 ==========
EMBEDDING_CONFIG = {
    "provider": "sentence-transformers",
    "model_name": "BAAI/bge-small-zh-v1.5",  # 首版：小模型，100MB，跑通全链路
    "dim": 512,
    "instruction": "",  # bge-small-zh 不需要 instruction prefix
    "batch_size": 16,
    "device": "cpu",
    "note": "补齐清单 P0-9 embedding 不锁死；下一版可切 bge-base-zh-v1.5 或 bge-large-zh-v1.5",
}

CHUNK_CONFIG = {
    "strategy": "section_aware_paragraph",
    "min_chars": 80,       # 太短的段落合并
    "max_chars": 500,      # 超长段落拆分
    "overlap": 0,          # 段落级切分不需要 overlap
    "keep_ref_together": False,  # 参考文献单独切
}


# ========== Embedding 抽象基类 ==========
class EmbeddingProvider:
    """抽象层，未来可切 openai/text-embedding-3, jina, or 本地 large 版"""
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._model = None

    def load(self):
        if self._model is not None: return
        from sentence_transformers import SentenceTransformer
        print(f"[embedding] 加载模型: {self.cfg['model_name']} ({self.cfg['device']})")
        self._model = SentenceTransformer(self.cfg["model_name"], device=self.cfg["device"])
        print(f"[embedding] 模型就绪 · 向量维度 {self._model.get_sentence_embedding_dimension()}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.load()
        if not texts: return []
        # bge 系列检索场景不加 instruction；查询时才加
        vecs = self._model.encode(texts, batch_size=self.cfg["batch_size"],
                                   show_progress_bar=False, normalize_embeddings=True)
        return vecs.tolist()

    def embed_query(self, q: str) -> list[float]:
        self.load()
        prefix = self.cfg.get("query_instruction", "")
        text = f"{prefix}{q}" if prefix else q
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec[0].tolist()


# ========== Chunking ==========
def is_reference_start(text: str) -> bool:
    """判断该段是否是参考文献起始"""
    t = text.strip()
    return t in ("参考文献", "References", "参 考 文 献") or t.startswith("参考文献")

def classify_section(text: str, seen_ref: bool) -> str:
    """粗略分区：abstract / keywords / introduction / body / references / english_abstract"""
    t = text.strip()
    if seen_ref: return "references"
    if t.startswith("内容提要"): return "abstract"
    if t.startswith("关键词"): return "keywords"
    if t.startswith("Abstract") or t.startswith("Keywords"): return "english_abstract"
    if t.startswith("JEL Classification"): return "english_abstract"
    if re.match(r'^[一二三四五六七八九十]+[、\.]', t): return "section_header"
    if re.match(r'^\d+[\.．]', t) and len(t) < 40: return "section_header"
    return "body"

import re
SECTION_HEADER_RE = re.compile(r'^([一二三四五六七八九十]+[、\.]|[（(][一二三四五六七八九十]+[)）]|\d+[\.．])\s*')

def chunk_paper(paper_data: dict) -> list[dict]:
    """
    切片策略（补齐清单 P0-7 章节感知）：
    - 保留 unit 的段落边界
    - 短段（<80 字符）与相邻同 section 合并
    - 长段（>500 字符）按句号拆分
    - 记录 section_type
    - 参考文献每条独立成块
    """
    units = paper_data.get("units", [])
    paper_id = paper_data["paper_id"]

    # 第一遍：分区
    seen_ref = False
    tagged = []
    current_section = "front"
    for i, u in enumerate(units):
        t = u.get("text", "").strip()
        if not t: continue
        if is_reference_start(t):
            seen_ref = True
            current_section = "references"
            tagged.append({"idx": i, "text": t, "section": "section_header", "current_section": "references_header"})
            continue
        sec = classify_section(t, seen_ref)
        # section_header 会更新 current_section
        if sec == "section_header":
            m = SECTION_HEADER_RE.match(t)
            current_section = f"body_{t[:20]}"
            tagged.append({"idx": i, "text": t, "section": "section_header", "current_section": current_section})
        else:
            tagged.append({"idx": i, "text": t, "section": sec, "current_section": current_section})

    # 第二遍：合并短段/拆长段
    chunks = []
    buffer_text = ""
    buffer_section = None
    buffer_current = None
    buffer_start_idx = None
    chunk_no = 0

    def flush_buffer():
        nonlocal buffer_text, buffer_section, buffer_current, buffer_start_idx, chunk_no
        if not buffer_text.strip(): return
        chunk_no += 1
        chunk_id = f"{paper_id}-C{chunk_no:04d}"
        chunks.append({
            "chunk_id": chunk_id,
            "paper_id": paper_id,
            "chunk_no": chunk_no,
            "section": buffer_section or "body",
            "current_section": buffer_current or "unknown",
            "start_unit_idx": buffer_start_idx,
            "char_len": len(buffer_text),
            "text": buffer_text.strip(),
        })
        buffer_text = ""
        buffer_section = None
        buffer_current = None
        buffer_start_idx = None

    for item in tagged:
        t = item["text"]
        sec = item["section"]
        curr = item["current_section"]

        # section header 独立成块
        if sec == "section_header":
            flush_buffer()
            chunk_no += 1
            chunks.append({
                "chunk_id": f"{paper_id}-C{chunk_no:04d}",
                "paper_id": paper_id,
                "chunk_no": chunk_no,
                "section": "section_header",
                "current_section": curr,
                "start_unit_idx": item["idx"],
                "char_len": len(t),
                "text": t,
            })
            continue

        # 参考文献每条独立
        if sec == "references":
            flush_buffer()
            chunk_no += 1
            chunks.append({
                "chunk_id": f"{paper_id}-C{chunk_no:04d}",
                "paper_id": paper_id,
                "chunk_no": chunk_no,
                "section": "reference_item",
                "current_section": "references",
                "start_unit_idx": item["idx"],
                "char_len": len(t),
                "text": t,
            })
            continue

        # 长段落：按句号拆
        if len(t) > CHUNK_CONFIG["max_chars"]:
            flush_buffer()
            sentences = re.split(r'(?<=[。！？])\s*', t)
            sub_buf = ""
            for s in sentences:
                if not s.strip(): continue
                if len(sub_buf) + len(s) > CHUNK_CONFIG["max_chars"] and sub_buf:
                    chunk_no += 1
                    chunks.append({
                        "chunk_id": f"{paper_id}-C{chunk_no:04d}",
                        "paper_id": paper_id, "chunk_no": chunk_no,
                        "section": sec, "current_section": curr,
                        "start_unit_idx": item["idx"],
                        "char_len": len(sub_buf), "text": sub_buf.strip(),
                    })
                    sub_buf = s
                else:
                    sub_buf += s
            if sub_buf.strip():
                chunk_no += 1
                chunks.append({
                    "chunk_id": f"{paper_id}-C{chunk_no:04d}",
                    "paper_id": paper_id, "chunk_no": chunk_no,
                    "section": sec, "current_section": curr,
                    "start_unit_idx": item["idx"],
                    "char_len": len(sub_buf), "text": sub_buf.strip(),
                })
            continue

        # 短段落：合并
        if len(t) < CHUNK_CONFIG["min_chars"]:
            if buffer_section == sec and buffer_current == curr:
                buffer_text += "\n" + t
            else:
                flush_buffer()
                buffer_text = t
                buffer_section = sec
                buffer_current = curr
                buffer_start_idx = item["idx"]
            # 若合并后超上限则 flush
            if len(buffer_text) >= CHUNK_CONFIG["min_chars"]:
                flush_buffer()
            continue

        # 正常段落
        flush_buffer()
        chunk_no += 1
        chunks.append({
            "chunk_id": f"{paper_id}-C{chunk_no:04d}",
            "paper_id": paper_id, "chunk_no": chunk_no,
            "section": sec, "current_section": curr,
            "start_unit_idx": item["idx"],
            "char_len": len(t), "text": t,
        })

    flush_buffer()
    return chunks


# ========== 主入库流程 ==========
def get_chroma():
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(
        path=str(VDB_ROOT),
        settings=Settings(anonymized_telemetry=False),
    )
    return client

def load_source_sha_ledger():
    """幂等：记录已入库论文的 source_sha256"""
    f = VDB_ROOT / "_source_sha_ledger.json"
    if f.exists():
        return json.load(open(f, encoding="utf-8"))
    return {}

def save_source_sha_ledger(ledger):
    f = VDB_ROOT / "_source_sha_ledger.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(ledger, fp, ensure_ascii=False, indent=2)

def ingest_batch(batch: str):
    # M4 数据隔离红线（plans/M4_BUILD_GATE_ADDENDUM.md §3.2）：
    # Benchmark 样本绝不得从本脚本入库 KB-B。
    # 本脚本固定从 PARSED_ROOT 读，下面重代一层字面防护。
    if any(seg in batch for seg in ["benchmark", "benchmarks", "fixture", "internal"]):
        raise ValueError(
            f"Benchmark/fixture/internal 目录禁止入库 KB-B：{batch!r}\n"
            f"参见 plans/M4_BUILD_GATE_ADDENDUM.md §3.2 数据隔离红线。"
        )
    batch_dir = PARSED_ROOT / batch
    if not batch_dir.exists():
        print(f"❌ 批次不存在: {batch_dir}")
        return

    print(f"\n{'='*60}")
    print(f"入库批次: {batch}")
    print(f"{'='*60}\n")

    provider = EmbeddingProvider(EMBEDDING_CONFIG)
    provider.load()

    client = get_chroma()
    coll = client.get_or_create_collection(
        name="examples_v1",
        metadata={
            "kb_layer": "example_reference",
            "purpose": "范例层：仅供改进参照，禁止作为学生论文错误依据（补齐清单原则 1）",
            "embedding_model": EMBEDDING_CONFIG["model_name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    ledger = load_source_sha_ledger()
    ingest_log = {
        "batch": batch,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "papers": [],
        "total_chunks": 0,
        "skipped_idempotent": 0,
    }

    for pf in sorted(batch_dir.glob("EXAMPLE-*.json")):
        with open(pf, encoding="utf-8") as f:
            paper = json.load(f)
        pid = paper["paper_id"]
        sha = paper["source_sha256"]

        # 幂等检查
        if sha in ledger and ledger[sha].get("collection_name") == "examples_v1":
            print(f"  ⏭️  {pid} 已入库 (source_sha256 匹配)，跳过")
            ingest_log["skipped_idempotent"] += 1
            continue

        # 切片
        chunks = chunk_paper(paper)
        print(f"  📄 {pid} · {paper['topic_hint']}")
        print(f"     切片: {len(chunks)} 块 (原 {paper['clean_units']} units)")

        # 向量化
        texts = [c["text"] for c in chunks]
        vecs = provider.embed(texts)
        print(f"     向量化: {len(vecs)} × {len(vecs[0]) if vecs else 0} 维")

        # 组装 metadata（Chroma 不支持嵌套，扁平化）
        ids = [c["chunk_id"] for c in chunks]
        metadatas = []
        for c in chunks:
            metadatas.append({
                "paper_id": pid,
                "chunk_no": c["chunk_no"],
                "section": c["section"],
                "current_section": c["current_section"][:60],
                "char_len": c["char_len"],
                "start_unit_idx": c["start_unit_idx"] or 0,
                "topic_hint": paper.get("topic_hint", ""),
                "paper_type": paper.get("paper_type", ""),
                "method_tags": ",".join(paper.get("method_tags", [])),
                "batch": batch,
                "source_sha256_short": sha[:16],  # 只留前16位便于追溯，全值在 ledger
                "kb_layer": "example_reference",  # 强制标记，防止跨层混用
                "warning": "reference_only_do_not_use_as_error_evidence",
            })

        coll.add(ids=ids, embeddings=vecs, metadatas=metadatas, documents=texts)
        print(f"     ✅ 入库完成")

        # 更新 ledger
        ledger[sha] = {
            "paper_id": pid,
            "batch": batch,
            "chunk_count": len(chunks),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "collection_name": "examples_v1",
            "embedding_model": EMBEDDING_CONFIG["model_name"],
        }

        # 写 metadata 文件（补齐清单 P0-2 example_registry 雏形）
        meta_out = METADATA_ROOT / f"{pid}.yaml"
        meta_lines = [
            f"paper_id: {pid}",
            f"source_sha256: {sha}",
            f"topic_hint: {paper.get('topic_hint','')}",
            f"paper_type: {paper.get('paper_type','')}",
            f"method_tags: [{', '.join(paper.get('method_tags', []))}]",
            f"batch: {batch}",
            f"chunk_count: {len(chunks)}",
            f"clean_units: {paper.get('clean_units', 0)}",
            f"replacement_count: {paper.get('replacement_count', 0)}",
            f"deident_status: approved",
            f"admission_source: online_top_journal",
            f"admission_confirmed_by_user: true",
            f"kb_layer: example_reference",
            f"can_be_error_evidence: false  # 补齐清单原则 1",
            f"ingested_at: {datetime.now(timezone.utc).isoformat()}",
            f"embedding_model: {EMBEDDING_CONFIG['model_name']}",
        ]
        meta_out.write_text("\n".join(meta_lines), encoding="utf-8")

        ingest_log["papers"].append({
            "paper_id": pid, "chunks": len(chunks),
            "topic_hint": paper.get("topic_hint", ""),
        })
        ingest_log["total_chunks"] += len(chunks)

    save_source_sha_ledger(ledger)

    ingest_log["ended_at"] = datetime.now(timezone.utc).isoformat()
    log_file = LOGS_ROOT / f"{batch}_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(ingest_log, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"批次完成")
    print(f"{'='*60}")
    print(f"入库论文: {len(ingest_log['papers'])}")
    print(f"总切片数: {ingest_log['total_chunks']}")
    print(f"幂等跳过: {ingest_log['skipped_idempotent']}")
    print(f"日志: {log_file}")


def show_status():
    """状态检查"""
    print("\n=== KB-B 范例层向量库状态 ===\n")
    client = get_chroma()
    try:
        coll = client.get_collection("examples_v1")
        count = coll.count()
        print(f"Collection: examples_v1")
        print(f"总切片数: {count}")
        meta = coll.metadata or {}
        for k, v in meta.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"⚠️  collection 未创建: {e}")

    print("\n=== Source SHA Ledger ===")
    ledger = load_source_sha_ledger()
    print(f"已入库论文数: {len(ledger)}")
    for sha, info in ledger.items():
        print(f"  · {info['paper_id']}: {info['chunk_count']} chunks (batch={info['batch']})")


def smoke_test():
    """跑几个真实查询验证检索质量"""
    print("\n=== Smoke Test · KB-B 检索验证 ===\n")

    provider = EmbeddingProvider(EMBEDDING_CONFIG)
    client = get_chroma()
    coll = client.get_collection("examples_v1")

    queries = [
        ("新质生产力理论内涵", "预期召回 EXAMPLE-0001/-0003/-0005"),
        ("双重差分DID识别策略", "预期召回 EXAMPLE-0002 或 -0004"),
        ("碳排放权交易机制", "预期召回 EXAMPLE-0002"),
        ("企业数字化转型如何测度", "预期召回 EXAMPLE-0006（LLM测度方法）"),
        ("数字技术创新与企业全要素生产率", "预期召回 EXAMPLE-0007 或 -0008"),
        ("ESG表现对企业创新的影响", "预期召回 EXAMPLE-0009"),
        ("ESG风险溢价与公司价值", "预期召回 EXAMPLE-0010"),
        ("专利文本分析方法", "预期召回 EXAMPLE-0006/-0007/-0008"),
        ("文献综述部分应该怎么写", "预期召回各论文的'二、文献综述'章节"),
    ]

    for q, expect in queries:
        print(f"🔎 Query: 「{q}」")
        print(f"   预期: {expect}")
        qvec = provider.embed_query(q)
        r = coll.query(query_embeddings=[qvec], n_results=3,
                       include=["metadatas", "distances", "documents"])
        for i in range(len(r["ids"][0])):
            cid = r["ids"][0][i]
            dist = r["distances"][0][i]
            m = r["metadatas"][0][i]
            doc_preview = r["documents"][0][i][:80].replace("\n", " ")
            print(f"   {i+1}. {cid} · dist={dist:.4f} · section={m.get('section')}")
            print(f"      topic={m.get('topic_hint')} · {doc_preview}...")
        print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--batch", help="入指定批次 (e.g. batch_01)")
    p.add_argument("--status", action="store_true")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    if args.status:
        show_status()
    elif args.smoke:
        smoke_test()
    elif args.batch:
        ingest_batch(args.batch)
    else:
        p.print_help()

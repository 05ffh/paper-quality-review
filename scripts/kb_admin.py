#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 · KB CRUD/快照/回滚 · 管理工具（v1）

对齐补齐清单 P0-13：CRUD + 快照 + 回滚

用法:
  # 状态
  python3 scripts/kb_admin.py status

  # 列出所有已入库论文
  python3 scripts/kb_admin.py list [--json]

  # 查看单篇详情
  python3 scripts/kb_admin.py show EXAMPLE-0006

  # 删除某篇（chunk + ledger）
  python3 scripts/kb_admin.py delete EXAMPLE-0006 [--yes]

  # 快照（把 active/ 打包备份到 snapshots/）
  python3 scripts/kb_admin.py snapshot [--tag v1.4.0-final] [--note "说明"]

  # 列出所有快照
  python3 scripts/kb_admin.py snapshots

  # 回滚到快照
  python3 scripts/kb_admin.py rollback <snapshot_dir> [--yes]

  # 完整性自检
  python3 scripts/kb_admin.py verify

安全约束:
- 破坏性操作（delete/rollback）必须 --yes 确认
- rollback 前会自动做一次快照
- ledger 与 collection 一致性由 verify 检查
"""
from __future__ import annotations
import argparse, json, os, sys, shutil, subprocess, tarfile
from pathlib import Path
from datetime import datetime, timezone
import warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VDB_ROOT = ROOT / "knowledge_base/vector_db"
ACTIVE_DIR = VDB_ROOT / "active"
SNAPSHOTS_DIR = VDB_ROOT / "snapshots"
LEDGER_FILE = ACTIVE_DIR / "_source_sha_ledger.json"
LOGS_DIR = ROOT / "knowledge_base/logs/admin"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION = "examples_v1"

# ---------- Chroma 延迟加载 ----------
_client = None
def get_chroma_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=str(ACTIVE_DIR))
    return _client

def get_collection():
    return get_chroma_client().get_collection(COLLECTION)


# ---------- ledger 读写 ----------
def load_ledger() -> dict:
    if not LEDGER_FILE.exists(): return {}
    return json.load(open(LEDGER_FILE, encoding="utf-8"))

def save_ledger(ledger: dict):
    with open(LEDGER_FILE, "w", encoding="utf-8") as fp:
        json.dump(ledger, fp, ensure_ascii=False, indent=2)


def _log_action(action: str, detail: dict):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    f = LOGS_DIR / f"{ts}_{action}.json"
    detail["_action"] = action
    detail["_at"] = ts
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(detail, fp, ensure_ascii=False, indent=2)
    return f


# ========== 命令实现 ==========

def cmd_status(args):
    """打印 KB-B 当前状态"""
    ledger = load_ledger()
    print("=" * 70)
    print(f"KB-B Vector DB Status")
    print("=" * 70)
    print(f"active dir      : {ACTIVE_DIR}")
    print(f"active exists   : {ACTIVE_DIR.exists()}")
    print(f"collection      : {COLLECTION}")
    print(f"ledger papers   : {len(ledger)}")

    if not ACTIVE_DIR.exists() or not any(ACTIVE_DIR.iterdir()):
        print("⚠️  active/ 为空或不存在")
        return

    try:
        coll = get_collection()
        c = coll.count()
        print(f"chroma chunks   : {c}")
    except Exception as e:
        print(f"❌ collection 加载失败: {e}")
        return

    # 磁盘占用
    du = subprocess.run(["du", "-sh", str(ACTIVE_DIR)], capture_output=True, text=True)
    print(f"active size     : {du.stdout.strip().split()[0] if du.returncode == 0 else '?'}")

    # 快照
    snaps = sorted([p for p in SNAPSHOTS_DIR.iterdir() if p.is_dir() or p.suffix == ".tar.gz"])
    print(f"snapshots       : {len(snaps)}")


def cmd_list(args):
    """列出所有论文"""
    ledger = load_ledger()
    rows = [{"sha": sha, **info} for sha, info in ledger.items()]
    rows.sort(key=lambda x: x.get("paper_id", ""))

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"{'paper_id':<15} {'batch':<10} {'chunks':>7}  ingested_at")
    print("-" * 70)
    for r in rows:
        print(f"{r['paper_id']:<15} {r['batch']:<10} {r['chunk_count']:>7}  {r['ingested_at']}")
    print(f"\n总计: {len(rows)} 篇")


def cmd_show(args):
    """查看单篇详情"""
    pid = args.paper_id
    ledger = load_ledger()
    entry = None
    for sha, info in ledger.items():
        if info.get("paper_id") == pid:
            entry = {"sha": sha, **info}
            break
    if not entry:
        print(f"❌ 未找到 {pid}")
        return 1

    print(f"=== {pid} ===")
    for k, v in entry.items():
        print(f"  {k}: {v}")

    # 尝试拉 chroma 里的 chunk 数验证
    try:
        coll = get_collection()
        r = coll.get(where={"paper_id": pid}, limit=10000)
        actual = len(r.get("ids", []))
        print(f"\nchroma 中该 paper 的 chunk 数: {actual}")
        if actual != entry.get("chunk_count"):
            print(f"⚠️  与 ledger 记录 ({entry['chunk_count']}) 不一致")

        # metadata 抽样
        if r["metadatas"]:
            print(f"\n首条 chunk metadata:")
            for k, v in list(r["metadatas"][0].items())[:15]:
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"⚠️  chroma 读取失败: {e}")


def cmd_delete(args):
    """删除某篇论文"""
    pid = args.paper_id
    ledger = load_ledger()

    target_sha = None
    for sha, info in ledger.items():
        if info.get("paper_id") == pid:
            target_sha = sha
            break
    if not target_sha:
        print(f"❌ 未找到 {pid}")
        return 1

    entry = ledger[target_sha]

    print(f"⚠️  即将删除:")
    print(f"    paper_id: {pid}")
    print(f"    chunks: {entry['chunk_count']}")
    print(f"    batch: {entry['batch']}")
    print(f"    ingested_at: {entry['ingested_at']}")

    if not args.yes:
        print(f"\n中止：请加 --yes 确认删除")
        return 2

    # 1. 删 chroma chunks
    try:
        coll = get_collection()
        r = coll.get(where={"paper_id": pid}, limit=10000)
        chunk_ids = r.get("ids", [])
        if chunk_ids:
            coll.delete(ids=chunk_ids)
            print(f"✅ 已删除 {len(chunk_ids)} 条 chunk")
    except Exception as e:
        print(f"❌ chroma 删除失败: {e}")
        return 1

    # 2. 从 ledger 移除
    del ledger[target_sha]
    save_ledger(ledger)
    print(f"✅ 已从 ledger 移除 {pid}")

    # 3. 日志
    log_file = _log_action("delete", {
        "paper_id": pid,
        "sha": target_sha,
        "removed_entry": entry,
        "chunks_removed": len(chunk_ids),
    })
    print(f"📝 操作日志: {log_file}")


def cmd_snapshot(args):
    """快照当前 active/ 到 snapshots/"""
    if not ACTIVE_DIR.exists():
        print("❌ active/ 不存在")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = args.tag or ts
    snap_name = f"snapshot_{tag}_{ts}"
    snap_dir = SNAPSHOTS_DIR / snap_name
    snap_dir.mkdir(parents=True, exist_ok=False)

    # 复制 active 内容
    for item in ACTIVE_DIR.iterdir():
        if item.is_dir():
            shutil.copytree(item, snap_dir / item.name)
        else:
            shutil.copy2(item, snap_dir / item.name)

    # 元信息
    ledger = load_ledger()
    try:
        coll_count = get_collection().count()
    except Exception:
        coll_count = -1

    meta = {
        "tag": tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": args.note or "",
        "ledger_papers": len(ledger),
        "collection_chunks": coll_count,
        "source_dir": str(ACTIVE_DIR),
    }
    with open(snap_dir / "_snapshot_meta.json", "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)

    # 磁盘占用
    du = subprocess.run(["du", "-sh", str(snap_dir)], capture_output=True, text=True)
    size = du.stdout.strip().split()[0] if du.returncode == 0 else "?"

    print(f"✅ 快照已创建")
    print(f"   路径: {snap_dir}")
    print(f"   标签: {tag}")
    print(f"   论文: {len(ledger)} 篇 · chunks: {coll_count} · 大小: {size}")
    _log_action("snapshot", meta)


def cmd_snapshots(args):
    """列出所有快照"""
    snaps = sorted([p for p in SNAPSHOTS_DIR.iterdir() if p.is_dir()])
    if not snaps:
        print("(无快照)")
        return
    for s in snaps:
        meta_f = s / "_snapshot_meta.json"
        if meta_f.exists():
            m = json.load(open(meta_f, encoding="utf-8"))
            print(f"  · {s.name}")
            print(f"      tag={m.get('tag')} · papers={m.get('ledger_papers')} "
                  f"· chunks={m.get('collection_chunks')} · at={m.get('created_at')}")
            if m.get("note"):
                print(f"      note: {m['note']}")
        else:
            print(f"  · {s.name}  (无元信息)")


def cmd_rollback(args):
    """回滚到指定快照"""
    snap = SNAPSHOTS_DIR / args.snapshot
    if not snap.exists() or not snap.is_dir():
        # 支持只给相对名
        alt = Path(args.snapshot)
        if alt.exists() and alt.is_dir():
            snap = alt
        else:
            print(f"❌ 快照不存在: {args.snapshot}")
            return 1

    meta_f = snap / "_snapshot_meta.json"
    if not meta_f.exists():
        print(f"❌ 缺少 _snapshot_meta.json，拒绝回滚：{snap}")
        return 1
    meta = json.load(open(meta_f, encoding="utf-8"))

    print(f"⚠️  即将回滚到快照:")
    print(f"    路径: {snap}")
    print(f"    tag: {meta.get('tag')}")
    print(f"    papers: {meta.get('ledger_papers')}")
    print(f"    chunks: {meta.get('collection_chunks')}")
    print(f"    创建时间: {meta.get('created_at')}")

    if not args.yes:
        print(f"\n中止：请加 --yes 确认回滚")
        return 2

    # 先自动快照当前 active 作为 pre-rollback 备份
    print(f"\n📦 回滚前自动备份当前 active/ ...")
    pre_args = argparse.Namespace(tag=f"pre_rollback_{meta.get('tag','')}", note="rollback 前自动备份")
    cmd_snapshot(pre_args)

    # 关闭 chroma client 以释放文件句柄
    global _client
    _client = None

    # 清空 active
    print(f"\n🧹 清空 active/ ...")
    for item in ACTIVE_DIR.iterdir():
        if item.name == "_snapshot_meta.json": continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 从 snapshot 拷回
    print(f"📥 从快照恢复 ...")
    for item in snap.iterdir():
        if item.name == "_snapshot_meta.json": continue
        if item.is_dir():
            shutil.copytree(item, ACTIVE_DIR / item.name)
        else:
            shutil.copy2(item, ACTIVE_DIR / item.name)

    print(f"✅ 回滚完成")
    _log_action("rollback", {
        "snapshot_dir": str(snap),
        "snapshot_meta": meta,
    })


def cmd_verify(args):
    """ledger 与 chroma 一致性自检"""
    ledger = load_ledger()
    print(f"=== KB-B 完整性自检 ===\n")

    if not ACTIVE_DIR.exists():
        print("❌ active/ 不存在")
        return 1

    try:
        coll = get_collection()
    except Exception as e:
        print(f"❌ collection 加载失败: {e}")
        return 1

    issues = []

    # 1. ledger 中每篇论文 chunk 数与 chroma 一致
    total_chunks_ledger = 0
    total_chunks_actual = 0
    ledger_pids = set()

    for sha, info in ledger.items():
        pid = info.get("paper_id")
        expected = info.get("chunk_count", 0)
        ledger_pids.add(pid)
        total_chunks_ledger += expected

        r = coll.get(where={"paper_id": pid}, limit=10000)
        actual = len(r.get("ids", []))
        total_chunks_actual += actual

        if actual != expected:
            issues.append(f"chunk 数不一致: {pid} ledger={expected} actual={actual}")

    # 2. chroma 里有没有 ledger 之外的 paper_id
    all_r = coll.get(limit=100000)
    chroma_pids = set()
    for m in all_r.get("metadatas", []):
        if m and m.get("paper_id"):
            chroma_pids.add(m["paper_id"])
    orphans = chroma_pids - ledger_pids
    if orphans:
        issues.append(f"chroma 中存在 ledger 未记录的 paper_id: {sorted(orphans)}")

    # 3. 强制 metadata 字段
    for m in all_r.get("metadatas", [])[:20]:  # 抽样 20 条
        if m.get("kb_layer") != "example_reference":
            issues.append(f"metadata kb_layer 异常: {m.get('paper_id')} kb_layer={m.get('kb_layer')}")
        # can_be_error_evidence 在 chunk metadata 中以 warning 字段存在
        # 因为 Chroma metadata 不支持 bool，kb_ingest 用字符串 warning 替代
        w = m.get("warning", "")
        if "reference_only" not in w and "do_not_use" not in w:
            issues.append(f"metadata warning 不包含 reference_only: {m.get('paper_id')} warning={w!r}")

    print(f"ledger papers    : {len(ledger)}")
    print(f"chroma pids      : {len(chroma_pids)}")
    print(f"ledger chunks    : {total_chunks_ledger}")
    print(f"actual chunks    : {total_chunks_actual}")
    print(f"issues           : {len(issues)}")
    if issues:
        print("\n❌ 发现问题:")
        for iss in issues:
            print(f"  · {iss}")
        return 1
    else:
        print("\n✅ 完整性 OK")


# ========== 入口 ==========

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("status")

    p_list = sub.add_parser("list")
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show")
    p_show.add_argument("paper_id")

    p_del = sub.add_parser("delete")
    p_del.add_argument("paper_id")
    p_del.add_argument("--yes", action="store_true")

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--tag")
    p_snap.add_argument("--note")

    sub.add_parser("snapshots")

    p_rb = sub.add_parser("rollback")
    p_rb.add_argument("snapshot")
    p_rb.add_argument("--yes", action="store_true")

    sub.add_parser("verify")

    args = ap.parse_args()
    handlers = {
        "status": cmd_status,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
        "snapshot": cmd_snapshot,
        "snapshots": cmd_snapshots,
        "rollback": cmd_rollback,
        "verify": cmd_verify,
    }
    if not args.cmd:
        ap.print_help(); return
    rc = handlers[args.cmd](args)
    if rc: sys.exit(rc)


if __name__ == "__main__":
    main()

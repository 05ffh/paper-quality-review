#!/usr/bin/env python3
"""KB 共享工具：零依赖 token 化、隐私扫描、文本清洗。"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

MAX_EXAMPLE_CHARS = 500
MIN_EXAMPLE_CHARS = 20

STOPWORDS = {
    "变量", "方法", "模型", "检验", "分析", "研究",
    "结果", "影响", "数据", "说明", "论文", "本文",
}

CONTACT_MARKERS = (
    "电子信箱", "电子邮箱", "邮政编码", "通讯作者", "作者简介", "作者单位",
)

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-＿]+(?:@|＠)[A-Za-z0-9.\-．]+", re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
POSTCODE_RE = re.compile(r"(邮政编码[：:\s]*)(\d{6})")
REFERENCE_HEADING_RE = re.compile(
    r"^(?:主要)?参考文献(?:目录)?$|^references?$", re.IGNORECASE,
)
APPENDIX_HEADING_RE = re.compile(r"^附录|^appendix", re.IGNORECASE)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def token_counts(text: str) -> Counter[str]:
    """字符 2-gram 计数。中文按 bigram，英文按 word。"""
    output: Counter[str] = Counter()
    for segment in re.findall(r"[一-鿿]+|[A-Za-z0-9]+", text):
        if re.fullmatch(r"[A-Za-z0-9]+", segment):
            if len(segment) >= 2:
                output[segment.lower()] += 1
        else:
            for index in range(len(segment) - 1):
                output[segment[index:index + 2]] += 1
    return output


def tokens(text: str) -> set[str]:
    return set(token_counts(text))


def is_reference_heading(text: str) -> bool:
    return bool(REFERENCE_HEADING_RE.fullmatch(normalize_text(text).strip("：: ")))


def is_appendix_heading(text: str) -> bool:
    return bool(APPENDIX_HEADING_RE.match(normalize_text(text)))


def sanitize_text(text: str) -> str:
    clean = normalize_text(text)
    clean = EMAIL_RE.sub("[联系方式已移除]", clean)
    clean = PHONE_RE.sub("[联系方式已移除]", clean)
    clean = ID_CARD_RE.sub("[身份号码已移除]", clean)
    clean = POSTCODE_RE.sub(r"\1[已移除]", clean)
    return clean


def looks_like_identity_block(text: str) -> bool:
    clean = normalize_text(text)
    marker_count = sum(marker in clean for marker in CONTACT_MARKERS)
    institution = any(term in clean for term in ("大学", "学院", "研究所", "研究院"))
    author_cue = any(term in clean for term in ("作者", "文责自负", "匿名审稿"))
    has_contact = bool(EMAIL_RE.search(clean) or PHONE_RE.search(clean))
    return (
        marker_count >= 1 and (institution or author_cue or has_contact)
    ) or (has_contact and institution)


def strip_leading_attribution(text: str) -> str:
    clean = sanitize_text(text)
    for separator in ("：", ":"):
        if separator not in clean:
            continue
        prefix, suffix = clean.split(separator, 1)
        if (
            len(prefix) <= 28
            and len(suffix.strip()) >= 8
            and (
                "、" in prefix
                or prefix.endswith("等")
                or prefix.endswith("等人")
                or bool(re.fullmatch(r"[一-鿿·]{2,6}", prefix))
            )
        ):
            return suffix.strip()
    return clean


def split_cards(text: str, max_chars: int = MAX_EXAMPLE_CHARS) -> list[str]:
    clean = sanitize_text(text)
    if len(clean) <= max_chars:
        return [clean] if len(clean) >= MIN_EXAMPLE_CHARS else []

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[。！？；!?;])", clean)
        if part.strip()
    ]
    cards: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > max_chars:
            if current:
                cards.append(current)
                current = ""
            cards.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if not sentence:
            continue
        proposed = sentence if not current else current + sentence
        if len(proposed) <= max_chars:
            current = proposed
        else:
            cards.append(current)
            current = sentence
    if current:
        cards.append(current)
    return [card.strip() for card in cards if len(card.strip()) >= MIN_EXAMPLE_CHARS]


def privacy_violations(texts: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for index, text in enumerate(texts):
        clean = normalize_text(text)
        if EMAIL_RE.search(clean):
            violations.append(f"card[{index}] contains email")
        if PHONE_RE.search(clean):
            violations.append(f"card[{index}] contains phone")
        if ID_CARD_RE.search(clean):
            violations.append(f"card[{index}] contains identity number")
        if looks_like_identity_block(clean):
            violations.append(f"card[{index}] contains author identity block")
    return violations

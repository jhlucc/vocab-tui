#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# word_ai.py
# 讲透一个英语单词：Tavily 检索 +（可选）OpenAI 兼容大模型；无密钥时自动降级到 dictionaryapi.dev + Wikipedia

from __future__ import annotations
import os
import re
import sys
import json
import datetime
import argparse
import textwrap
from typing import Dict, Any, List, Optional

try:
    import requests
except Exception:
    print("需要安装 requests：  pip install requests")
    sys.exit(1)

# ===== util =====

def now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def wrap(s: str, width: int = 100) -> str:
    return "\n".join(textwrap.wrap(s, width=width, replace_whitespace=False)) if s else s

def trim(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    s = s.strip().replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")

# ===== free sources (fallback) =====

def fetch_dictionaryapi(word: str) -> Dict[str, Any]:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "error": f"{r.status_code} {r.text[:160]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_wikipedia_summary(word: str, lang: str = "en") -> Dict[str, Any]:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{word}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "word-ai/1.1"})
        if r.status_code == 200:
            j = r.json()
            return {"ok": True, "title": j.get("title"), "extract": j.get("extract")}
        return {"ok": False, "error": f"{r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ===== tavily =====

def tavily_available() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))

def build_web_query(word: str) -> str:
    return (
        f"{word} meaning and usage; collocations; common phrases; "
        f"etymology; synonyms antonyms; example sentences; register; CEFR"
    )

def fetch_tavily(query: str, max_results: int = 6, depth: str = "advanced") -> Dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"ok": False, "error": "TAVILY_API_KEY missing"}
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": depth if depth in ("basic", "advanced") else "advanced",
        "include_answer": True,
        "max_results": max(1, min(int(max_results), 15)),
        "include_images": False,
        "include_raw_content": False,
        "topic": "general",
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            j = r.json()
            items = [{
                "title": it.get("title") or "",
                "url": it.get("url") or "",
                "content": it.get("content") or "",
                "score": it.get("score") or 0,
            } for it in j.get("results", [])]
            return {"ok": True, "items": items, "answer": j.get("answer")}
        return {"ok": False, "error": f"{r.status_code} {r.text[:160]}"}  # noqa
    except Exception as e:
        return {"ok": False, "error": str(e)}

def tavily_refs_for_prompt(tav: Dict[str, Any], limit: int = 380) -> str:
    if not tav or not tav.get("ok"):
        return ""
    lines: List[str] = []
    if tav.get("answer"):
        lines.append(f"(Tavily answer) {trim(tav['answer'], 600)}")
    for i, it in enumerate(tav.get("items", [])[:8], 1):
        title = trim(it.get("title") or "", 120)
        url = it.get("url") or ""
        snippet = trim(it.get("content") or "", limit)
        if url:
            lines.append(f"[{i}] {title} — {url}\n    {snippet}")
    return "\n".join(lines)

def tavily_refs_for_footer(tav: Dict[str, Any], max_items: int) -> Optional[str]:
    if not tav or not tav.get("ok"):
        return None
    links: List[str] = []
    ans = tav.get("answer")
    if ans:
        links.append("> Tavily 摘要： " + trim(ans, 240))
    for it in tav.get("items", [])[:max_items]:
        title = trim(it.get("title") or it.get("url"), 80)
        url = it.get("url") or ""
        if url:
            links.append(f"- [{title}]({url})")
    return "\n".join(links) if links else None

# ===== llm (OpenAI compatible) =====

def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))

def call_openai_chat(messages: List[Dict[str, str]], model: str = "gpt-4o-mini",
                     temperature: float = 0.3, max_tokens: int = 2200) -> str:
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
    api_key = os.getenv("OPENAI_API_KEY")
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "temperature": temperature, "messages": messages, "max_tokens": max_tokens}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"].strip()

def dictapi_summary(dic: Dict[str, Any]) -> str:
    if not dic or not dic.get("ok"):
        return ""
    try:
        d = dic["data"][0]
        phon = [ph.get("text") for ph in d.get("phonetics", []) if ph.get("text")]
        senses: List[str] = []
        for m in d.get("meanings", []):
            pos = m.get("partOfSpeech", "")
            defs = [dd.get("definition", "") for dd in m.get("definitions", [])[:2]]
            if defs:
                senses.append(f"{pos}: " + "; ".join(defs))
        out: List[str] = []
        if phon:
            # 去重
            seen = []
            for p in phon:
                if p not in seen:
                    seen.append(p)
            out.append("Phonetics: " + " / ".join(seen))
        if senses:
            out.append("Senses: " + " | ".join(senses))
        return " | ".join(out)
    except Exception:
        return ""

def build_messages(word: str, lang: str, n_sent: int,
                   tavily_block: str, wiki_en: str, wiki_zh: str, dict_block: str) -> List[Dict[str, str]]:
    refs: List[str] = []
    if tavily_block: refs.append("## Web search (Tavily)\n" + tavily_block)
    if wiki_en: refs.append("## Wikipedia EN\n" + trim(wiki_en, 800))
    if wiki_zh: refs.append("## Wikipedia ZH\n" + trim(wiki_zh, 800))
    if dict_block: refs.append("## DictionaryAPI (summary)\n" + dict_block)
    ref_block = "\n\n".join(refs) if refs else "（无外部参考）"

    system = {
        "role": "system",
        "content": (
            "你是面向中文学习者的英汉双语词典编辑与写作教练。"
            "请用中文为主输出，结构清晰，可直接做学习笔记。"
            "当外部资料与常识冲突时，以外部资料为准，并说明不确定性。"
        )
    }
    user = {
        "role": "user",
        "content": f"""
请以 Markdown 输出，**讲透**英语单词：**{word}**。

下面是已检索到的参考资料（仅供对齐事实，不要求逐条引用）：
{ref_block}

需要的板块：
1. 音标/重音（英/美，如可）
2. 核心义项+中文解释（按词性；每义项补 1 个常见搭配）
3. 常见搭配/短语/固定搭配（≥6）
4. 同义词/近义词 与 反义词（各 5–10，必要时简注差异）
5. 语域与用法提醒（正式/非正式、易错点）
6. 词源与词族（派生词/词缀）
7. 高质量例句：{n_sent} 条（地道多样；每句附中文；如可标注 CEFR）
8. 我来造句：给出 {max(3, n_sent//2)} 条“造句模板”（中文提示+英文句型）
9. 练习：① 克漏字；② 近义辨析单选；③ 中译英（都给答案）
10. 延伸语块：4–6 个 collocations（3–8 词，附中文提示）
"""
    }
    return [system, user]

# ===== render & save =====

def render_llm(md_body: str, word: str, footnote: Optional[str]) -> str:
    head = f"# {word}\n> AI 讲解（{now_ts()} 生成）\n\n"
    tail = ("\n---\n**参考（自动检索）**\n" + footnote + "\n") if footnote else ""
    return head + md_body.strip() + tail

def render_fallback(word: str, dic: Dict[str, Any], wiki_en: Dict[str, Any],
                    wiki_zh: Dict[str, Any], lang: str, n_sent: int,
                    footnote: Optional[str]) -> str:
    lines = [f"# {word}", f"> 联网后备（{now_ts()}）\n"]

    if dic.get("ok"):
        d = dic["data"][0]
        phon = []
        for ph in d.get("phonetics", []):
            t = ph.get("text")
            if t and t not in phon:
                phon.append(t)
        if phon:
            lines += ["## 音标", "- " + " / ".join(phon)]
        lines.append("## 核心义项（dictionaryapi.dev）")
        for m in d.get("meanings", []):
            pos = m.get("partOfSpeech", "")
            defs = [dd.get("definition", "") for dd in m.get("definitions", [])]
            if defs:
                lines.append(f"- **{pos}**: {defs[0]}")
                for ext in defs[1:3]:
                    lines.append(f"  - 其他：{ext}")

    if wiki_en.get("ok") or wiki_zh.get("ok"):
        lines.append("## 维基百科摘要")
        if wiki_en.get("ok"): lines.append("- EN: " + wrap(wiki_en["extract"]))
        if wiki_zh.get("ok"): lines.append("- ZH: " + wrap(wiki_zh["extract"]))

    lines.append("## 例句（自动生成，供参考）")
    templates = [
        f"I used the word '{word}' in a simple sentence.",
        f"The meaning of '{word}' depends on the context.",
        f"People often learn '{word}' through examples and practice.",
        f"Here is another example that clarifies '{word}'.",
        f"This phrase with '{word}' is common in daily speech."
    ]
    for i, s in enumerate(templates[:max(3, n_sent)], 1):
        lines.append(f"{i}. {s}  \n   - 中文参考：依语境理解")

    lines += [
        "## 练习",
        "1) 克漏字：I ____ this word by writing three sentences.（示例：learned）",
        "2) 选择：Which is closest to the meaning of the word? (A) … (B) … (C) …",
        f"3) 中译英：请用 **{word}** 造句，并给出中文翻译。",
    ]
    if footnote:
        lines += ["\n---", "**参考（自动检索）**", footnote]
    return "\n".join(lines) + "\n"

def save_md(md: str, word: str, out_dir: str = "ai_notes") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{word}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path

# ===== pipeline =====

def run(word: str, lang: str = "zh", sentences: int = 6, model: str = "gpt-4o-mini",
        save: bool = False, plain: bool = False, search: str = "auto",
        max_web: int = 6, depth: str = "advanced") -> int:
    word = word.strip()

    use_tav = (search == "tavily") or (search == "auto" and tavily_available())
    tav_res: Optional[Dict[str, Any]] = None
    footnote: Optional[str] = None
    if use_tav:
        tav_res = fetch_tavily(build_web_query(word), max_results=max_web, depth=depth)
        if tav_res.get("ok"):
            footnote = tavily_refs_for_footer(tav_res, max_items=max_web)

    dic = fetch_dictionaryapi(word)
    wiki_en = fetch_wikipedia_summary(word, "en")
    wiki_zh = fetch_wikipedia_summary(word, "zh")

    if llm_available():
        tav_block = tavily_refs_for_prompt(tav_res) if (tav_res and tav_res.get("ok")) else ""
        dic_block = dictapi_summary(dic) if dic.get("ok") else ""
        wiki_en_text = wiki_en.get("extract") if wiki_en.get("ok") else ""
        wiki_zh_text = wiki_zh.get("extract") if wiki_zh.get("ok") else ""
        msgs = build_messages(word, lang, sentences, tav_block, wiki_en_text, wiki_zh_text, dic_block)
        try:
            md_body = call_openai_chat(msgs, model=model, temperature=0.3, max_tokens=2200)
            md = render_llm(md_body, word, footnote)
        except Exception as e:
            md = render_fallback(word, dic, wiki_en, wiki_zh, lang, sentences, footnote)
            md += f"\n> ⚠️ LLM 调用失败：{e}\n"
    else:
        md = render_fallback(word, dic, wiki_en, wiki_zh, lang, sentences, footnote)

    if save:
        path = save_md(md, word)
        print(f"[saved] {path}")

    if plain:
        print(re.sub(r'^#{1,6}\s*', '', md, flags=re.M))
    else:
        try:
            from rich.console import Console
            from rich.markdown import Markdown
            Console().print(Markdown(md))
        except Exception:
            print(md)
    return 0

# ===== cli =====

def main():
    p = argparse.ArgumentParser(prog="word_ai", description="讲透一个英语单词（Tavily + LLM；无密钥自动降级）")
    p.add_argument("word", help="要讲解的英文单词")
    p.add_argument("--lang", default="zh", help="输出语言（默认 zh）")
    p.add_argument("--sentences", type=int, default=6, help="例句数量（默认 6）")
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                   help="OpenAI 兼容模型名")
    p.add_argument("--search", choices=["auto", "tavily", "off"], default="auto",
                   help="联网检索模式（auto/tavily/off）")
    p.add_argument("--max-web", type=int, default=6, help="Tavily 结果条数（1-15）")
    p.add_argument("--depth", choices=["basic", "advanced"], default="advanced",
                   help="Tavily 搜索深度")
    p.add_argument("--save", action="store_true", help="保存为 ai_notes/<word>.md")
    p.add_argument("--plain", action="store_true", help="以纯文本输出（便于 TUI 弹窗）")
    args = p.parse_args()

    return sys.exit(run(
        args.word, lang=args.lang, sentences=args.sentences, model=args.model,
        save=args.save, plain=args.plain, search=args.search,
        max_web=args.max_web, depth=args.depth
    ))

if __name__ == "__main__":
    main()

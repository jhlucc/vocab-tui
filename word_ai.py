#!/usr/bin/env python3
# -*- coding: utf-8 -*-
 

import os, sys, json, argparse, textwrap, datetime, re
from typing import Dict, Any, List, Optional, Iterable

try:
    import requests
except Exception:
    print("需要安装 requests：  pip install requests")
    sys.exit(1)

 

def now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def wrap_lines(s: str, width=100):
    return "\n".join(textwrap.wrap(s, width=width, replace_whitespace=False)) if s else s

def trim(s: str, n: int) -> str:
    if s is None:
        return ""
    s = s.strip().replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")

# ============================================================================
# .env 读取（零依赖实现）
# ============================================================================

_DOTENV: Dict[str, str] = {}

def _strip_quotes(v: str) -> str:
    v = v.strip()
    if (len(v) >= 2) and ((v[0] == v[-1]) and v[0] in ("'", '"')):
        return v[1:-1]
    return v

def _load_dotenv_from(path: str) -> Dict[str, str]:
    envs: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
                if not m:
                    continue
                k, v = m.group(1), _strip_quotes(m.group(2).strip())
                envs[k] = v
    except Exception:
        pass
    return envs

def _candidate_env_paths() -> List[str]:
    paths: List[str] = []
    # 1) 可执行文件目录（PyInstaller onefile / 普通 python 均可）
    if getattr(sys, "frozen", False):
        paths.append(os.path.join(os.path.dirname(sys.executable), ".env"))
    # 2) 脚本所在目录
    paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    # 3) 当前工作目录
    paths.append(os.path.join(os.getcwd(), ".env"))
    # 去重，保序
    seen = set(); uniq = []
    for p in paths:
        if p not in seen:
            seen.add(p); uniq.append(p)
    return uniq

def _init_dotenv():
    global _DOTENV
    for p in _candidate_env_paths():
        if os.path.exists(p):
            _DOTENV = _load_dotenv_from(p)
            break

def _get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """优先读系统环境变量，其次 .env"""
    v = os.getenv(key)
    if v is not None and str(v).strip() != "":
        return v.strip()
    return _DOTENV.get(key, default)

# 提前初始化 .env
_init_dotenv()

# ============================================================================
# 数据源：免费后备
# ============================================================================

def fetch_dictionaryapi(word: str) -> Dict[str, Any]:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return {"ok": True, "source": "dictionaryapi.dev", "data": r.json()}
        return {"ok": False, "source": "dictionaryapi.dev", "error": f"{r.status_code} {r.text[:120]}"}  # noqa
    except Exception as e:
        return {"ok": False, "source": "dictionaryapi.dev", "error": str(e)}

def fetch_wikipedia_summary(word: str, lang="en") -> Dict[str, Any]:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{word}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "word-ai/1.1"})
        if r.status_code == 200:
            j = r.json()
            return {"ok": True, "source": f"wikipedia:{lang}", "title": j.get("title"), "extract": j.get("extract")}
        return {"ok": False, "source": f"wikipedia:{lang}", "error": f"{r.status_code}"}
    except Exception as e:
        return {"ok": False, "source": f"wikipedia:{lang}", "error": str(e)}

# ============================================================================
# 数据源：Tavily 搜索
# ============================================================================

def tavily_available() -> bool:
    return bool(_get_env("TAVILY_API_KEY"))

def fetch_tavily(query: str, max_results: int = 6, depth: str = "advanced") -> Dict[str, Any]:
    """
    Tavily Web Search API：
      POST https://api.tavily.com/search
      payload:
        api_key, query, search_depth("basic"/"advanced"), include_answer(bool),
        max_results(int), include_images(bool), include_raw_content(bool) 等
    返回：
      { ok: bool, items: [ {title,url,content,score}, ... ], answer?: str }
    """
    api_key = _get_env("TAVILY_API_KEY")
    if not api_key:
        return {"ok": False, "error": "TAVILY_API_KEY missing"}
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": depth if depth in ("basic", "advanced") else "advanced",
        "include_answer": True,
        "max_results": max(1, min(int(max_results), 15)),
        "topic": "general",
        "include_images": False,
        "include_raw_content": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            j = r.json()
            items = []
            for it in j.get("results", []):
                items.append({
                    "title": it.get("title") or "",
                    "url": it.get("url") or "",
                    "content": it.get("content") or "",
                    "score": it.get("score") or 0,
                })
            return {"ok": True, "items": items, "answer": j.get("answer")}
        return {"ok": False, "error": f"{r.status_code} {r.text[:160]}"}  # noqa
    except Exception as e:
        return {"ok": False, "error": str(e)}

def build_web_query_for_word(word: str) -> str:
    # 针对词汇学习定制的检索串（英文更容易命中优质资料）
    return (
        f"{word} meaning and usage; collocations; common phrases; etymology; "
        f"synonyms antonyms; example sentences; register and pitfalls; CEFR"
    )

# ============================================================================
# LLM（OpenAI 兼容）
# ============================================================================

def llm_available() -> bool:
    return bool(_get_env("OPENAI_API_KEY"))

def call_openai_chat(messages: List[Dict[str, str]], model: str = "gpt-4o-mini",
                     temperature: float = 0.3, max_tokens: int = 2000) -> str:
    # 兼容两种变量名：OPENAI_BASE_URL / OPENAI_API_BASE
    base_url = _get_env("OPENAI_BASE_URL") or _get_env("OPENAI_API_BASE") or "https://api.openai.com"
    api_key = _get_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未设置")
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "temperature": temperature, "messages": messages, "max_tokens": max_tokens}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"].strip()

# ============================================================================
# Prompt 与渲染
# ============================================================================

def format_tavily_refs(tavily: Dict[str, Any], limit_snippet: int = 400) -> str:
    if not tavily or not tavily.get("ok"):
        return ""
    lines = []
    ans = tavily.get("answer")
    if ans:
        lines.append(f"(Tavily preliminary answer) {trim(ans, 600)}")
    for i, it in enumerate(tavily.get("items", [])[:8], 1):
        title = trim(it.get("title") or "", 120)
        url = it.get("url") or ""
        snippet = trim(it.get("content") or "", limit_snippet)
        if url:
            lines.append(f"[{i}] {title} — {url}\n    {snippet}")
    return "\n".join(lines)

def format_dictapi_refs(dic: Dict[str, Any]) -> str:
    if not dic or not dic.get("ok"):
        return ""
    try:
        d = dic["data"][0]
        phon = []
        for ph in d.get("phonetics", []):
            t = ph.get("text")
            if t and t not in phon:
                phon.append(t)
        senses = []
        for m in d.get("meanings", []):
            pos = m.get("partOfSpeech","")
            defs = [dd.get("definition","") for dd in m.get("definitions", [])[:2]]
            if defs:
                senses.append(f"{pos}: " + "; ".join(defs))
        out = []
        if phon:
            out.append("Phonetics: " + " / ".join(phon))
        if senses:
            out.append("Senses: " + " | ".join(senses))
        return " | ".join(out)
    except Exception:
        return ""

def build_llm_messages(word: str, lang: str, sentence_count: int,
                       tavily_refs: str, wiki_en: str, wiki_zh: str, dict_refs: str) -> List[Dict[str, str]]:
    refs_text = []
    if tavily_refs: refs_text.append("## Web search (Tavily)\n" + tavily_refs)
    if wiki_en: refs_text.append("## Wikipedia EN\n" + trim(wiki_en, 800))
    if wiki_zh: refs_text.append("## Wikipedia ZH\n" + trim(wiki_zh, 800))
    if dict_refs: refs_text.append("## DictionaryAPI (summary)\n" + dict_refs)
    ref_block = "\n\n".join(refs_text) if refs_text else "（无外部参考）"

    system = {
        "role": "system",
        "content": (
            "你是一名面向中文学习者的英汉双语词典编辑与写作教练。"
            "请用**中文为主**输出，必要的英语保留。风格清晰、结构化、可直接放到学习笔记。"
            "当外部资料和常识冲突时，优先以外部资料为准并注明不确定性。"
        )
    }
    user = {
        "role": "user",
        "content": f"""
请以 Markdown 输出，**讲透**英语单词：**{word}**。

你可以参考下面已经检索/抓取到的外部资料（仅供对齐事实，不是必须逐条引用）：
{ref_block}

### 需要的板块（都请尽量给出，如信息不足可省略）：
1. **音标/重音**：英/美发音（若可）。
2. **核心义项+中文释义**：分词性列出，每个义项给一句**自己的中文解释**，并补 1 个**常见搭配**。
3. **常见搭配/短语/固定搭配**：至少 6 条（动词短语、介词搭配、名词搭配混合）。
4. **同义词/近义表达** 与 **反义词**：各 5–10 个，必要时简注差异。
5. **语域与用法提醒**：正式/非正式、易错点、常见误用。
6. **词源与词族**：简述词源，列出派生词或常见词缀。
7. **高质量例句**：{sentence_count} 条。地道自然，覆盖不同义项和语法结构；每句**给出中文翻译**；如可，标注 CEFR 级别（A2-C2）。
8. **我来造句**：给出 {max(3, sentence_count//2)} 条“造句模板”（中文提示 + 英文句型）。
9. **三道练习**：① 克漏字；② 近义词辨析选择题；③ 中文提示英译（都给标准答案）。
10. **延伸语块**：4–6 个高频语块或常和它一起出现的词（collocations），每个 3–8 词，附中文提示。
"""
    }
    return [system, user]

# 渲染/保存
def render_markdown_from_llm(md: str, word: str, web_refs_footnote: Optional[str]) -> str:
    header = f"# {word}\n> AI 讲解（{now_ts()} 生成）\n\n"
    footer = ("\n---\n**参考（自动检索）**\n" + web_refs_footnote + "\n") if web_refs_footnote else ""
    return header + md.strip() + footer

def render_from_fallback(word: str, dictapi: Dict[str, Any], wiki_en: Dict[str, Any],
                         wiki_zh: Dict[str, Any], lang: str, sentence_count: int,
                         web_refs_footnote: Optional[str]) -> str:
    lines = [f"# {word}", f"> 联网后备（{now_ts()}）\n"]
    # 词典
    if dictapi.get("ok"):
        d = dictapi["data"][0]
        phon = []
        for ph in d.get("phonetics", []):
            t = ph.get("text")
            if t and t not in phon:
                phon.append(t)
        if phon:
            lines += ["## 音标", "- " + " / ".join(phon)]
        lines.append("## 核心义项（dictionaryapi.dev）")
        for m in d.get("meanings", []):
            pos = m.get("partOfSpeech","")
            defs = [dd.get("definition","") for dd in m.get("definitions", [])]
            if defs:
                lines.append(f"- **{pos}**: {defs[0]}")
                for ext in defs[1:3]:
                    lines.append(f"  - 其他：{ext}")
    # 维基
    if wiki_en.get("ok") or wiki_zh.get("ok"):
        lines.append("## 维基百科摘要")
        if wiki_en.get("ok"): lines.append("- EN: " + wrap_lines(wiki_en["extract"]))
        if wiki_zh.get("ok"): lines.append("- ZH: " + wrap_lines(wiki_zh["extract"]))
    # 粗糙例句
    lines.append("## 例句（自动生成，供参考）")
    templates = [
        f"I used the word '{word}' in a simple sentence.",
        f"The meaning of '{word}' depends on the context.",
        f"People often learn '{word}' through examples and practice.",
        f"Here is another example that clarifies '{word}'.",
        f"This phrase with '{word}' is quite common in daily speech."
    ]
    for i, s in enumerate(templates[:max(3, sentence_count)], 1):
        lines.append(f"{i}. {s}  \n   - 中文参考：请结合语境理解")
    # 练习
    lines += [
        "## 练习",
        "1) 克漏字：I ____ this word by writing three sentences. （答案示例：learned）",
        "2) 选择：Which is closest to the meaning of the word? (A) … (B) … (C) …",
        f"3) 英译中：请用 **{word}** 造一个句子，并给出中文翻译。",
    ]
    if web_refs_footnote:
        lines += ["\n---", "**参考（自动检索）**", web_refs_footnote]
    return "\n".join(lines) + "\n"

def save_markdown(md: str, word: str, out_dir="ai_notes") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{word}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path

# ============================================================================
# 主流程
# ============================================================================

def run(word: str, lang: str = "zh", sentences: int = 6, model: str = "gpt-4o-mini",
        save: bool = False, plain: bool = False, search_mode: str = "auto",
        max_web: int = 6, depth: str = "advanced") -> int:
    word = word.strip()

    #  先做联网检索（Tavily 或后备）
    use_tavily = (search_mode == "tavily") or (search_mode == "auto" and tavily_available())
    tavily_result = None
    web_refs_footnote = None
    if use_tavily:
        q = build_web_query_for_word(word)
        tavily_result = fetch_tavily(q, max_results=max_web, depth=depth)
        if tavily_result.get("ok"):
            links = []
            for it in tavily_result.get("items", [])[:max_web]:
                title = trim(it.get("title") or it.get("url"), 80)
                url = it.get("url") or ""
                if url:
                    links.append(f"- [{title}]({url})")
            ans = tavily_result.get("answer")
            if ans:
                links.insert(0, "> Tavily 摘要： " + trim(ans, 240))
            web_refs_footnote = "\n".join(links) if links else None

    dictapi = fetch_dictionaryapi(word)
    wiki_en = fetch_wikipedia_summary(word, "en")
    wiki_zh = fetch_wikipedia_summary(word, "zh")

    # 再用 LLM 组织高质量讲解
    if llm_available():
        tavily_block = format_tavily_refs(tavily_result, 380) if (tavily_result and tavily_result.get("ok")) else ""
        dict_block = format_dictapi_refs(dictapi) if dictapi.get("ok") else ""
        wiki_en_text = wiki_en.get("extract") if wiki_en.get("ok") else ""
        wiki_zh_text = wiki_zh.get("extract") if wiki_zh.get("ok") else ""
        messages = build_llm_messages(word, lang, sentences, tavily_block, wiki_en_text, wiki_zh_text, dict_block)
        try:
            md_body = call_openai_chat(messages, model=model, temperature=0.3, max_tokens=2200)
            md = render_markdown_from_llm(md_body, word, web_refs_footnote)
        except Exception as e:
            md = render_from_fallback(word, dictapi, wiki_en, wiki_zh, lang, sentences, web_refs_footnote)
            md += f"\n> ⚠️ LLM调用失败：{e}\n"
    else:
        md = render_from_fallback(word, dictapi, wiki_en, wiki_zh, lang, sentences, web_refs_footnote)

    # 3) 输出/保存
    if save:
        path = save_markdown(md, word)
        print(f"[saved] {path}")

    if plain:
        text = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
        print(text)
    else:
        try:
            from rich.console import Console
            from rich.markdown import Markdown
            Console().print(Markdown(md))
        except Exception:
            print(md)
    return 0

def main():
    p = argparse.ArgumentParser(description="一键讲透英语单词（支持 Tavily 搜索 + 大模型 + .env）")
    p.add_argument("word", help="要讲解的英文单词")
    p.add_argument("--lang", default="zh", help="输出语言（默认 zh）")
    p.add_argument("--sentences", type=int, default=6, help="例句数量（默认 6）")
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                   help="OpenAI 兼容模型名（默认 gpt-4o-mini）")
    p.add_argument("--save", action="store_true", help="保存为 ai_notes/<word>.md")
    p.add_argument("--plain", action="store_true", help="以纯文本输出（便于 TUI 展示）")
    p.add_argument("--search", choices=["auto", "tavily", "off"], default="auto",
                   help="联网检索模式：auto(默认)/tavily/off")
    p.add_argument("--max-web", type=int, default=6, help="Tavily 最大结果数（默认 6，最多 15）")
    p.add_argument("--depth", choices=["basic", "advanced"], default="advanced",
                   help="Tavily 搜索深度（默认 advanced）")
    args = p.parse_args()
    return sys.exit(run(args.word, lang=args.lang, sentences=args.sentences,
                        model=args.model, save=args.save, plain=args.plain,
                        search_mode=args.search, max_web=args.max_web, depth=args.depth))

if __name__ == "__main__":
    main()

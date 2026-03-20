import json
import re

from bs4 import BeautifulSoup
from openai import AsyncOpenAI

DEFAULT_MODEL = "google/gemini-3-flash-preview"

ANALYZE_PROMPT = """你係一個網頁結構分析器。以下係一個產品頁面嘅 HTML 結構摘要。

分析以下兩個問題：

1. **needs_javascript**: 呢個頁面需唔需要 JavaScript 渲染先可以攞到產品內容？
   - 如果見到 SPA framework markers（`__NUXT__`, `__NEXT_DATA__`, `ng-app`, `data-reactroot` 但 body 內容好少）→ true
   - 如果見到空嘅 container div（`<div id="app"></div>`、`<div id="root"></div>` 冇實際內容）→ true
   - 如果 body 已經有豐富嘅產品文字內容 → false

2. **extraction_strategy**: 應該用邊種策略提取產品描述？
   - `"rule_based"`: 頁面用語義化 HTML（h2/h3/p/ul/table 結構清晰），適合用 CSS selector 提取
   - `"ai_extraction"`: 頁面用多層 div 嵌套、hash/random class names、非語義化結構，需要 AI 理解內容

只回傳 JSON，唔好加其他文字：
{{"needs_javascript": true/false, "extraction_strategy": "rule_based"/"ai_extraction"}}

---
URL: {url}

{structural_sample}
"""


def _prepare_structural_sample(raw_html: str) -> str:
    """Extract a structural sample from raw HTML for AI analysis.

    Returns ~15-20KB containing:
    - <head> excerpt (~5KB): framework markers, meta tags, JSON-LD
    - <body> excerpt (~10KB): content structure (scripts/styles/SVGs removed)
    - Class/ID inventory: top classes and IDs for pattern recognition
    """
    soup = BeautifulSoup(raw_html, 'lxml')
    parts = []

    # Head excerpt (~5KB)
    head = soup.find('head')
    if head:
        head_html = str(head)
        if len(head_html) > 5000:
            head_html = head_html[:5000]
            last_close = head_html.rfind('>')
            if last_close > 4000:
                head_html = head_html[:last_close + 1]
        parts.append(f"=== HEAD (truncated) ===\n{head_html}")

    # Body excerpt (~10KB) — remove script/style/svg content
    body = soup.find('body')
    if body:
        for tag in body.find_all(['script', 'style', 'svg', 'noscript']):
            tag.decompose()
        body_html = str(body)
        if len(body_html) > 10000:
            body_html = body_html[:10000]
            last_close = body_html.rfind('>')
            if last_close > 8000:
                body_html = body_html[:last_close + 1]
        parts.append(f"=== BODY (truncated, scripts/styles removed) ===\n{body_html}")

    # Class/ID inventory
    all_classes = {}
    all_ids = []
    for tag in soup.find_all(True):
        for cls in tag.get('class', []):
            all_classes[cls] = all_classes.get(cls, 0) + 1
        tag_id = tag.get('id')
        if tag_id and tag_id not in all_ids:
            all_ids.append(tag_id)

    top_classes = sorted(all_classes.items(), key=lambda x: -x[1])[:50]
    top_ids = all_ids[:20]
    if top_classes or top_ids:
        inventory = "=== CLASS/ID INVENTORY ==="
        if top_classes:
            inventory += f"\nTop classes: {', '.join(c[0] for c in top_classes)}"
        if top_ids:
            inventory += f"\nIDs: {', '.join(top_ids)}"
        parts.append(inventory)

    return "\n\n".join(parts)


async def analyze_page_structure(
    raw_html: str, url: str, api_key: str, model: str | None = None
) -> dict | None:
    """Analyze page structure with AI to determine fetch method and extraction strategy.

    Returns {"needs_javascript": bool, "extraction_strategy": "rule_based"|"ai_extraction"}
    or None if analysis fails (caller should fall back to heuristics).
    """
    try:
        structural_sample = _prepare_structural_sample(raw_html)
        if not structural_sample or len(structural_sample) < 100:
            return None

        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        response = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": ANALYZE_PROMPT.format(
                        url=url,
                        structural_sample=structural_sample,
                    ),
                }
            ],
        )
        content = response.choices[0].message.content
        if not content:
            return None

        # Strip markdown code block if present
        content = content.strip()
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        result = json.loads(content)

        # Validate expected fields
        if not isinstance(result.get("needs_javascript"), bool):
            return None
        if result.get("extraction_strategy") not in ("rule_based", "ai_extraction"):
            return None

        return result
    except Exception:
        return None

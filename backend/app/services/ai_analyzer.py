import json
import re

from bs4 import BeautifulSoup
from openai import AsyncOpenAI

DEFAULT_MODEL = "anthropic/claude-3.5-haiku"

ANALYZE_PROMPT = """你係一個網頁結構分析器。以下係一個產品頁面嘅 HTML 結構摘要。

分析以下問題，回傳 JSON：

1. **needs_javascript** (bool): 頁面需唔需要 JavaScript 渲染先可以攞到產品內容？
   - SPA framework markers（`__NUXT__`, `__NEXT_DATA__`, `ng-app`, `data-reactroot` 但 body 內容好少）→ true
   - 空嘅 container div（`<div id="app"></div>`、`<div id="root"></div>` 冇實際內容）→ true
   - body 已有豐富產品文字內容 → false

2. **extraction_strategy** ("rule_based" | "ai_extraction"): 應該用邊種策略提取產品描述？
   - `"rule_based"`: 語義化 HTML（h2/h3/p/ul/table 結構清晰），CSS selector 就夠
   - `"ai_extraction"`: 多層 div 嵌套、hash/random class names、非語義化結構

3. **content_selectors** (list of CSS selectors, 最多5個): 邊啲 CSS selector 可以搵到主要產品描述內容區域？
   - 搵包含產品特色、功能描述、詳細介紹嘅容器
   - 用你喺 HTML 入面見到嘅實際 class name / ID
   - 例如: ["#product-description", ".ProductFeature_wrapper__abc12", "section.features"]
   - 如果搵唔到明確嘅 selector，返回空 list []

4. **noise_selectors** (list of CSS selectors, 最多5個): 邊啲元素係噪音應該移除？
   - 搵非產品內容嘅區塊（推薦產品、相關商品、評論、FAQ、footer 推廣等）
   - 只列呢個頁面特有嘅 selector，唔使列通用嘅 header/footer/nav
   - 如果冇特別嘅噪音 selector，返回空 list []

5. **content_structure** ("semantic" | "div_heavy" | "mixed"): 產品內容嘅 HTML 結構類型？
   - "semantic": 主要用 h2/h3/p/ul/table 等語義標籤
   - "div_heavy": 主要用 div 嵌套 + 隨機/hash class names
   - "mixed": 部分語義、部分 div

6. **content_language** (string): 頁面內容嘅主要語言？
   - 例如 "zh-TW", "zh-CN", "en", "ja" 等

只回傳 JSON，唔好加其他文字：
{{"needs_javascript": true/false, "extraction_strategy": "rule_based"/"ai_extraction", "content_selectors": [...], "noise_selectors": [...], "content_structure": "semantic"/"div_heavy"/"mixed", "content_language": "xx"}}

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

        # Validate required fields (return None if invalid)
        if not isinstance(result.get("needs_javascript"), bool):
            return None
        if result.get("extraction_strategy") not in ("rule_based", "ai_extraction"):
            return None

        # Normalize new fields with safe defaults
        if not isinstance(result.get("content_selectors"), list):
            result["content_selectors"] = []
        else:
            result["content_selectors"] = [
                s for s in result["content_selectors"]
                if isinstance(s, str) and 0 < len(s) <= 100
            ][:5]

        if not isinstance(result.get("noise_selectors"), list):
            result["noise_selectors"] = []
        else:
            result["noise_selectors"] = [
                s for s in result["noise_selectors"]
                if isinstance(s, str) and 0 < len(s) <= 100
            ][:5]

        if result.get("content_structure") not in ("semantic", "div_heavy", "mixed"):
            result["content_structure"] = "mixed"

        if not isinstance(result.get("content_language"), str):
            result["content_language"] = ""

        return result
    except Exception:
        return None

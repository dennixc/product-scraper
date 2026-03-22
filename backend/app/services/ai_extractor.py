from openai import AsyncOpenAI
from bs4 import BeautifulSoup

MAX_HTML_CHARS = 100_000

REMOVE_SELECTORS = [
    'header', 'footer', 'nav',
    '[class*="cookie"]', '[class*="consent"]',
    '[class*="breadcrumb"]', '[class*="sidebar"]', '[class*="newsletter"]',
    '[class*="subscribe"]', '[class*="social"]', '[class*="share"]',
    '[class*="upsell"]', '[class*="cross-sell"]',
    '[id*="cookie"]', '[id*="consent"]', '[id*="breadcrumb"]',
    '[id*="sidebar"]', '[id*="newsletter"]',
    'script', 'style', 'noscript', 'iframe',
]

EXTRACT_PROMPT = """你係一個產品描述提取器。以下係「{product_name}」產品頁面嘅 HTML 內容。
{analysis_hints}
你嘅工作：從中提取所有同產品相關嘅描述內容，包括功能特色、技術規格、賣點等。

規則：
1. 只保留產品描述相關內容
2. 移除導航、頁尾、版權、cookie 提示、廣告等
3. 移除重複內容（同一段出現多次只保留一次）
4. 輸出格式：clean HTML，只用 h2/h3/h4, p, ul/ol/li, table/tr/td/th, strong/em, br
5. 保持原文語言，唔好翻譯
6. 唔好加入原文冇出現過嘅內容

直接回傳 HTML，唔好加 markdown code block 或解釋。

---
{html}
"""

DEFAULT_MODEL = "google/gemini-3-flash-preview"


def _build_analysis_hints(analysis: dict | None) -> str:
    if not analysis:
        return ""
    parts = []
    if analysis.get("content_selectors"):
        parts.append(f"產品描述可能喺以下區域: {', '.join(analysis['content_selectors'])}")
    if analysis.get("content_structure"):
        structure_desc = {
            "semantic": "頁面用語義化 HTML (h2/h3/p/ul/table)",
            "div_heavy": "頁面用多層 div 嵌套、可能有 hash class names",
            "mixed": "頁面混合語義標籤同 div 嵌套",
        }
        desc = structure_desc.get(analysis["content_structure"])
        if desc:
            parts.append(desc)
    if analysis.get("content_language"):
        parts.append(f"內容主要語言: {analysis['content_language']}")
    if not parts:
        return ""
    return "\n## 頁面結構提示\n" + "\n".join(f"- {p}" for p in parts)


def _prepare_html(raw_html: str, analysis: dict | None = None) -> str:
    """Clean and truncate raw HTML for AI extraction."""
    soup = BeautifulSoup(raw_html, 'lxml')

    for selector in REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Remove site-specific noise identified by AI analyzer
    if analysis and analysis.get("noise_selectors"):
        for selector in analysis["noise_selectors"]:
            try:
                for el in soup.select(selector):
                    el.decompose()
            except Exception:
                pass

    main = soup.find('main') or soup.find('body') or soup
    html = str(main)

    if len(html) <= MAX_HTML_CHARS:
        return html
    truncated = html[:MAX_HTML_CHARS]
    last_close = truncated.rfind('>')
    if last_close > MAX_HTML_CHARS * 0.8:
        truncated = truncated[:last_close + 1]
    return truncated


async def extract_description_with_ai(
    raw_html: str,
    product_name: str,
    api_key: str,
    model: str | None = None,
    analysis: dict | None = None,
    extra_instructions: str = "",
) -> str:
    """用 AI 從 raw HTML 提取產品描述。

    如果 AI call 失敗，return 空 string（caller 會 fall back 用 rule-based 結果）。
    """
    try:
        prepared = _prepare_html(raw_html, analysis)
        if not prepared or len(prepared) < 100:
            return ""

        prompt = EXTRACT_PROMPT.format(
            product_name=product_name,
            analysis_hints=_build_analysis_hints(analysis),
            html=prepared,
        )
        if extra_instructions:
            prompt += f"\n\n## 用戶額外指示\n{extra_instructions}"

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
                    "content": prompt,
                }
            ],
        )
        result = response.choices[0].message.content
        return result.strip() if result else ""
    except Exception:
        return ""

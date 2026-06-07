import asyncio
import logging
from bs4 import BeautifulSoup, Tag
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

MAX_HTML_CHARS = 100_000


def _truncate_html(html: str) -> str:
    """Truncate HTML at ~100KB, trying to break at a tag boundary."""
    if len(html) <= MAX_HTML_CHARS:
        return html
    truncated = html[:MAX_HTML_CHARS]
    last_close = truncated.rfind('>')
    if last_close > MAX_HTML_CHARS * 0.8:
        truncated = truncated[:last_close + 1]
    return truncated


_ALLOWED_TAGS = {"h2", "h3", "p", "ul", "li", "strong"}
_STRIP_TAGS = {"hr", "style", "script", "br", "div", "span"}


def _clean_ai_output(html: str) -> str:
    """Normalize AI output: unwrap container, drop noise tags, strip style/class attrs.

    Defensive — AI doesn't always follow the new prompt's restrictions (legacy
    inline styles or hr separators can leak through).
    """
    soup = BeautifulSoup(html, "html.parser")

    # If the AI wrapped everything in a single top-level <div>, unwrap it.
    top_tags = [c for c in soup.children if isinstance(c, Tag)]
    if len(top_tags) == 1 and top_tags[0].name == "div":
        top_tags[0].unwrap()

    # Drop noise tags entirely (extract removes element + content).
    # br/div/span are unwrapped instead (preserve inner text).
    for tag in soup.find_all(["hr", "style", "script"]):
        tag.decompose()
    for tag in soup.find_all(["br", "div", "span"]):
        tag.unwrap()

    # Remove empty heading/paragraph blocks left after unwrap/decompose.
    for tag in soup.find_all(["p", "h2", "h3", "li"]):
        if not tag.get_text(strip=True):
            tag.decompose()

    # Strip style/class on every remaining element.
    for tag in soup.find_all(True):
        tag.attrs.pop("style", None)
        tag.attrs.pop("class", None)

    return str(soup).strip()


WRAPPER_STYLE_BLOCK = """<style>
  .shopline-custom-product-desc h2 {
    font-size: 1.6em;
    margin-top: 1.8em !important;
    margin-bottom: 0.8em !important;
    font-weight: bold;
    color: #111;
  }
  .shopline-custom-product-desc h3 {
    font-size: 1.25em;
    margin-top: 1.5em !important;
    margin-bottom: 0.6em !important;
    font-weight: bold;
    color: #222;
  }
  .shopline-custom-product-desc p {
    margin-top: 0 !important;
    margin-bottom: 1.2em !important;
  }
  .shopline-custom-product-desc ul {
    margin-top: 0 !important;
    margin-bottom: 1.2em !important;
    padding-left: 20px !important;
    list-style-type: disc !important;
  }
  .shopline-custom-product-desc li {
    margin-bottom: 0.6em !important;
    line-height: 1.5;
  }
  .shopline-custom-product-desc strong {
    font-weight: bold;
  }
</style>"""


def _wrap_shopline_styles(html: str) -> str:
    """Wrap cleaned AI content in the scoped class container + style block."""
    return (
        '<div class="shopline-custom-product-desc" '
        'style="line-height: 1.6; color: #333; font-family: sans-serif;">'
        f'{WRAPPER_STYLE_BLOCK}'
        f'{html}'
        '</div>'
    )


SHOPLINE_PROMPT = """你係一個 Shopline 商品描述 HTML 生成器。將以下產品資料轉換為純 semantic HTML。輸出之後會自動包入帶 CSS class 嘅 styled container（你唔需要關心 styling）。

## 產品資料

**產品名稱**: {product_name}
**產品型號**: {product_model}
**摘要**: {summary}

**詳細描述 HTML**:
{description_html}

## 輸出規則（嚴格）

- **只可以用呢 6 個 tag**：`h2`, `h3`, `p`, `ul`, `li`, `strong`
- **唔加任何 `style` 或 `class` attribute**
- **唔用**：`hr`, `div`, `span`, `br`, `table`, `img`, `style`, `script`
- **唔包 wrapper container** — 直接由第一個結構元素開始
- **唔用 markdown code block 包裹**

## 內容結構

1. 第一個 element：`<h2>` 含產品名稱 + 型號（例如 "ASUS RT-BE59"）
2. 第二個 element：`<p>` 一句摘要（從產品資料嘅「摘要」嚟）
3. 之後：將詳細描述按主題分 section
   - `<h2>` 做大 section 標題（例如「性能」「安全」「功能」）
   - `<h3>` 做 sub-section 標題（個別 feature）
   - `<p>` 描述段落
   - `<ul>` + `<li>` 列點
   - `<strong>` 強調重要字眼

## 內容禁止事項

- 唔加原文冇出現過嘅產品資訊
- 唔加 spec table / 規格表 / 技術參數表（另外處理）
- 唔用 emoji（冇 ⚡🌐📡💎）

## 語言

輸出語言必須同「詳細描述 HTML」一致。英文就全英文、中文就全中文，唔好混合。

直接 output HTML（由第一個 `<h2>` 開始），唔好加任何解釋。
"""

DEFAULT_MODEL = "z-ai/glm-5"


async def generate_shopline_html(
    product_name: str,
    product_model: str,
    summary: str,
    description_html: str,
    api_key: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
    flags: dict | None = None,
) -> str:
    """用 OpenRouter AI 生成 Shopline semantic HTML，post-process 後包入 CSS scope。

    失敗時 return 紅色錯誤 div（graceful fallback）。
    """
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=90,
    )
    extra = {}
    if reasoning_effort:
        extra["extra_body"] = {"reasoning": {"effort": reasoning_effort}}
    prompt_content = SHOPLINE_PROMPT.format(
        product_name=product_name,
        product_model=product_model,
        summary=summary,
        description_html=_truncate_html(description_html),
    )

    last_error = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt_content}],
                **extra,
            )
            result = response.choices[0].message.content
            if result:
                result = result.strip()
                if result.startswith("```html"):
                    result = result[7:]
                elif result.startswith("```"):
                    result = result[3:]
                if result.endswith("```"):
                    result = result[:-3]
                result = result.strip()
                result = _clean_ai_output(result)
                return _wrap_shopline_styles(result)
            return ""
        except Exception as e:
            last_error = e
            logger.warning("Shopline HTML generation attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(2)

    logger.exception("Shopline HTML generation failed after 3 attempts", exc_info=last_error)
    error_msg = str(last_error).replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<div style="padding:24px;border:1px solid #e00;border-radius:8px;margin:16px 0">'
        f'<p style="color:#e00;font-weight:600;margin:0 0 8px 0">Shopline HTML 生成失敗</p>'
        f'<p style="color:#666;font-size:14px;margin:0">{error_msg}</p>'
        f'</div>'
    )

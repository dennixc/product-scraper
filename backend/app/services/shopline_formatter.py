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


def _is_empty_spacer(tag: Tag) -> bool:
    """True if tag is an empty <p>/<br> already acting as a spacer."""
    if tag.name == "br":
        return True
    if tag.name == "p" and not tag.get_text(strip=True):
        return True
    return False


def _add_shopline_spacing(html: str) -> str:
    """Insert <p><br></p> between top-level sibling blocks for Shopline editor.

    Shopline 嘅 editor 會 strip / override 我哋輸出嘅 inline margin styling，導致
    section 視覺逼埋。物理上加空段落做佔位 editor 唔會 collapse。

    Skip 規則：相鄰任意一邊係 <hr>（已經係視覺分隔）或已經係空 spacer。
    """
    soup = BeautifulSoup(html, "html.parser")
    container: Tag = soup.find("div") or soup
    children = [c for c in container.children if isinstance(c, Tag)]
    if len(children) < 2:
        return str(soup)

    for i in range(len(children) - 1):
        cur, nxt = children[i], children[i + 1]
        if cur.name == "hr" or nxt.name == "hr":
            continue
        if _is_empty_spacer(cur) or _is_empty_spacer(nxt):
            continue
        spacer = soup.new_tag("p")
        spacer.append(soup.new_tag("br"))
        cur.insert_after(spacer)

    return str(soup)


SHOPLINE_PROMPT = """你係一個 Shopline 商品描述 HTML 生成器。將產品資料轉換為專業簡潔、高可讀性嘅 HTML，可以直接貼入 Shopline 商品描述編輯器。

## 產品資料

**產品名稱**: {product_name}
**產品型號**: {product_model}
**摘要**: {summary}

**詳細描述 HTML**:
{description_html}

## 設計規則

### 只可以用嘅 HTML 元素
div, h2, h3, p, ul, li, hr, span, strong

### 所有 styling 必須用 inline styles

### 字體（統一）
font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'PingFang TC', 'Noto Sans TC', sans-serif

### 色彩（只用呢四個）
- 主文字：color: #1d1d1f
- 次要文字：color: #6e6e73
- 分隔線：border-color: #d2d2d7
- 背景：永遠係白色，唔好用任何背景色

### 字體大小（固定）
- 產品名：font-size: 32px; font-weight: 700; line-height: 1.2; color: #1d1d1f
- 型號／標籤：font-size: 14px; font-weight: 400; color: #6e6e73; letter-spacing: 0.5px
- 摘要：font-size: 15px; line-height: 1.7; color: #6e6e73
- Section 標題：font-size: 22px; font-weight: 700; line-height: 1.3; color: #1d1d1f
- 內文：font-size: 15px; font-weight: 400; line-height: 1.7; color: #1d1d1f

### 間距（固定，唔好自己調）
- 最外層容器：max-width: 720px; margin: 0 auto; padding: 0 20px
- Section 之間：margin-top: 48px
- 標題同內文之間：margin-top: 16px
- 段落之間：margin-top: 12px
- 分隔線：margin: 48px 0; border: none; border-top: 1px solid #d2d2d7

## 頁面結構（嚴格按以下順序）

### 第一區：產品標題
- 產品名稱（h2，32px 粗體）
- 型號顯示喺產品名下面（14px，次要色，letter-spacing: 0.5px）
- 一句摘要（15px，次要色，margin-top: 12px）
- 底部一條 hr 分隔線

### 第二區：產品特點（主要內容）
- 將產品嘅主要特點拆分成獨立段落
- 每個特點：一個 h3（22px 粗體）+ 一至兩段 p（15px）
- 特點之間用 hr 分隔線分開
- 文字左對齊（唔好置中）
- 如果原文有列表形式嘅內容，用 ul > li 呈現
- ul 嘅 style：margin-top: 12px; padding-left: 20px
- li 嘅 style：font-size: 15px; line-height: 1.7; color: #1d1d1f; margin-top: 6px

## 禁止事項

- 唔好用 emoji（冇 ⚡🌐📡💎）
- 唔好用 card layout（冇 box-shadow、border-radius 卡片）
- 唔好用任何彩色（冇藍色、紅色、金色、綠色）
- 唔好用 background-color（全白底）
- 唔好用 border-left accent bar
- 唔好用 <style> 標籤
- 唔好用 <table> 標籤
- 唔好用 <img> 標籤
- 唔好用 text-align: center
- 唔好加入原文冇嘅產品資訊
- 唔好加入規格表／配置表／spec table（呢啲會另外處理）
- 唔好用 markdown code block 包裹輸出

## 語言

輸出語言必須同「詳細描述 HTML」嘅語言一致。如果描述係英文，所有標題同內文都要用英文。如果係中文，就用中文。唔好混合語言。

直接回傳完整嘅 HTML，由 <div> 開始，唔好加任何解釋。
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
    """用 OpenRouter AI 生成 Shopline 兼容嘅帶 inline styles HTML。

    失敗時 return 空 string（graceful fallback）。
    """
    flags = flags or {}
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
                if flags.get("add_shopline_spacing"):
                    result = _add_shopline_spacing(result)
                return result
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

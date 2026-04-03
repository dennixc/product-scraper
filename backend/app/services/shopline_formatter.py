import logging
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


SHOPLINE_PROMPT = """你係一個 Shopline 商品描述 HTML 生成器。將產品資料轉換為簡約、高可讀性嘅 HTML，可以直接貼入 Shopline 商品描述編輯器。

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
- 分隔線：border-color: #e0e0e0
- 背景：永遠係白色，唔好用任何背景色

### 字體大小（固定）
- 產品名：font-size: 28px; font-weight: 700; line-height: 1.2; color: #1d1d1f
- 型號／標籤：font-size: 14px; font-weight: 400; color: #6e6e73
- 摘要：font-size: 16px; line-height: 1.6; color: #6e6e73
- Section 標題：font-size: 20px; font-weight: 700; line-height: 1.3; color: #1d1d1f
- 內文：font-size: 16px; font-weight: 400; line-height: 1.6; color: #1d1d1f
- 規格標籤：font-size: 14px; color: #6e6e73
- 規格內容：font-size: 14px; color: #1d1d1f

### 間距（固定，唔好自己調）
- 最外層容器：max-width: 780px; margin: 0 auto; padding: 0 16px
- Section 之間：margin-top: 32px
- 標題同內文之間：margin-top: 12px
- 段落之間：margin-top: 10px
- 分隔線：margin: 32px 0; border: none; border-top: 1px solid #e0e0e0

## 頁面結構（嚴格按以下順序）

### 第一區：產品標題
- 產品名稱（h2，28px 粗體）
- 型號顯示喺產品名下面（14px，次要色）
- 一句摘要（16px，次要色，margin-top: 8px）
- 底部一條 hr 分隔線

### 第二區：產品特點（主要內容）
- 將產品嘅主要特點拆分成獨立段落
- 每個特點：一個 h3（20px 粗體）+ 一至兩段 p（16px）
- 特點之間用 hr 分隔線分開
- 文字左對齊（唔好置中）
- 如果原文有列表形式嘅內容，用 ul > li 呈現

### 第三區：規格（如有）
- 標題用 h3（20px 粗體），寫「規格」或英文 "Specifications"（跟原文語言）
- 用 ul > li 列出每項規格
- 每個 li 入面：用 strong 標籤包住規格名稱，後面跟數值
- 例如：<li style="..."><strong>重量：</strong>1.2 kg</li>
- 如果規格有多個分類，每組用 h3 做小標題

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
- 唔好用 markdown code block 包裹輸出

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
) -> str:
    """用 OpenRouter AI 生成 Shopline 兼容嘅帶 inline styles HTML。

    失敗時 return 空 string（graceful fallback）。
    """
    try:
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=90,
        )
        response = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": SHOPLINE_PROMPT.format(
                        product_name=product_name,
                        product_model=product_model,
                        summary=summary,
                        description_html=_truncate_html(description_html),
                    ),
                }
            ],
        )
        result = response.choices[0].message.content
        if result:
            # 去掉可能嘅 markdown code block 包裹
            result = result.strip()
            if result.startswith("```html"):
                result = result[7:]
            elif result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            return result.strip()
        return ""
    except Exception as e:
        logger.exception("Shopline HTML generation failed")
        error_msg = str(e).replace("<", "&lt;").replace(">", "&gt;")
        return (
            f'<div style="padding:24px;border:1px solid #e00;border-radius:8px;margin:16px 0">'
            f'<p style="color:#e00;font-weight:600;margin:0 0 8px 0">Shopline HTML 生成失敗</p>'
            f'<p style="color:#666;font-size:14px;margin:0">{error_msg}</p>'
            f'</div>'
        )

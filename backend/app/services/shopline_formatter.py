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


SHOPLINE_PROMPT = """你係一個 Shopline 商品描述 HTML 生成器。你嘅工作係將產品資料轉換為一段高端、簡約嘅 HTML 產品頁面，風格參考 Apple.com 嘅產品介紹頁。所有 styling 必須用 inline styles，可以直接貼入 Shopline 商品描述編輯器。

## 產品資料

**產品名稱**: {product_name}
**產品型號**: {product_model}
**摘要**: {summary}

**詳細描述 HTML**:
{description_html}

## 設計系統

### 字體
所有元素統一用：font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', 'PingFang TC', 'Noto Sans TC', sans-serif

### 色彩（黑白灰為主，金色點綴）
- 深色背景：background-color: rgb(0, 0, 0)；文字用 color: rgb(245, 245, 247)
- 淺色背景：background-color: rgb(245, 245, 247)；文字用 color: rgb(29, 29, 31)
- 白色背景：background-color: rgb(255, 255, 255)；文字用 color: rgb(29, 29, 31)
- 次要文字：color: rgb(134, 134, 139)
- 金色 accent：#b4956a — 只用喺分隔線同個別重點文字，克制使用

### 字體大小
- 產品名稱（hero 標題）：font-size: 48px; font-weight: 600; letter-spacing: -0.5px; line-height: 1.1
- 產品 tagline（hero 副標題）：font-size: 21px; font-weight: 400; line-height: 1.47; color: rgb(134, 134, 139)
- Section 大標題：font-size: 32px; font-weight: 600; letter-spacing: -0.3px; line-height: 1.12
- Section 內文：font-size: 17px; font-weight: 400; line-height: 1.47
- 分類標籤（如有）：font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: rgb(134, 134, 139)

### 間距
- 每個 section 嘅 padding：padding: 72px 24px
- 內容區域最大寬度：max-width: 820px; margin: 0 auto
- 標題同內文之間：margin-top: 16px
- 段落之間：margin-top: 12px

## 頁面結構（嚴格按以下順序）

### 第一區：Hero Section
- 黑色背景（rgb(0, 0, 0)），文字置中
- 產品名稱用大標題樣式（48px, font-weight 600, 白色）
- 下面放產品摘要或一句話 tagline（21px, rgb(134, 134, 139)）
- 如果有型號，用更細嘅字體顯示喺產品名上方（12px, uppercase, rgb(134, 134, 139)）
- 上下留白要充足（padding: 80px 24px）

### 第二區：核心賣點 Sections
- 將產品嘅主要特點分成獨立嘅 section
- **深色同淺色背景交替出現**（第一個用 rgb(245, 245, 247)，第二個用 rgb(0, 0, 0)，如此類推）
- 每個 section 入面：一個大標題（32px, font-weight 600）加一至兩段描述文字（17px）
- 文字全部置中（text-align: center）
- 每個 section 都要有充足嘅上下 padding（padding: 72px 24px）
- 內容用 max-width: 820px; margin: 0 auto 限制寬度

### 第三區：詳細規格／細節（如有足夠資料）
- 白色背景（rgb(255, 255, 255)）
- 將剩餘嘅技術細節、規格或功能列表整理喺呢度
- 用簡潔嘅文字列表或分組呈現，唔好用表格
- 如果有多組資訊，可以用金色分隔線（border-top: 1px solid #b4956a; margin: 32px 0）分開
- 每組可以有一個小標題（font-size: 21px; font-weight: 600）同內容

## 絕對唔好做嘅嘢

- **唔好用 emoji icon**（冇 ⚡🌐📡💎 呢啲）
- **唔好用 card layout**（冇 box-shadow、冇 border-radius 卡片、冇背景色卡片）
- **唔好用藍色或其他彩色**（唔好用 #2563eb、唔好用彩色 border、唔好用彩色背景；只可以用金色 #b4956a 做 accent）
- **唔好用 border-left accent bar**
- **唔好用 <style> 標籤**——全部 inline styles
- **唔好加入原文冇出現嘅產品資訊**（可以重新組織排版，但內容必須來自輸入資料）
- **唔好用 markdown code block 包裹輸出**——直接輸出純 HTML
- **唔好用圖片 tag**（<img>）

## 響應式要求

- 所有 section 用 max-width: 100% 確保唔會超出畫面
- 內容區用 max-width: 820px; margin: 0 auto 置中
- padding 用 24px 左右，確保手機有邊距

直接回傳完整嘅 HTML 代碼，由 <div> 開始，唔好加任何解釋。
"""

DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324"


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

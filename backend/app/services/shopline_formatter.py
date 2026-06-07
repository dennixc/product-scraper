import asyncio
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


SHOPLINE_PROMPT = """你是一位專業的電商網頁前端工程師，專門為 Shopline 平台優化產品描述的 HTML 代碼。

Shopline 系統會自動過濾 `<style>` 標籤並覆蓋外部 CSS，因此你必須【嚴格遵守】以下規則，將所有樣式「完全寫死」在行內樣式（Inline Styles）中，以確保排版在 Shopline 網頁上 100% 不會變形、不會黐埋一齊。

### 🛠️ 核心排版規則：
1. 絕對不能使用任何 `<style>` 標籤，也不能使用 `class="..."`。
2. 必須使用 `margin-bottom` 或 `margin-top` 來控制段落與標題之間的距離，絕對不能依賴瀏覽器預設的間距。
3. 所有文字顏色、字體大小、行距必須用 inline style 寫死。

---

### 🎨 HTML 標籤與 Inline Style 對照表：

請將輸入的文案，嚴格依照以下 HTML 結構與樣式進行轉換：

1. 【最外層容器 (Wrapper Div)】
   <div style="line-height: 1.8; color: #333; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; max-width: 800px; margin: 0 auto; padding: 10px;">
   （所有內容必須包在這個 div 入面）

2. 【主標題 (h2)】- 用於大章節、主要賣點
   <h2 style="font-size: 24px; font-weight: bold; margin-top: 40px; margin-bottom: 20px; color: #111; border-left: 4px solid #0056b3; padding-left: 12px; line-height: 1.4;">標題文字</h2>
   * 如果標題內有需要強調的關鍵字，請使用：<strong style="color: #0056b3;">強調文字</strong>

3. 【副標題 (h3)】- 用於小節、細項功能
   <h3 style="font-size: 19px; font-weight: bold; margin-top: 28px; margin-bottom: 14px; color: #222; line-height: 1.4;">副標題文字</h3>

4. 【普通段落 (p)】
   <p style="margin-top: 0; margin-bottom: 24px; line-height: 1.8; color: #444; font-size: 16px;">段落文字</p>

5. 【備註 / 註釋 / 免責聲明 (p)】- 用於斜體、灰色小字
   <p style="margin-top: 0; margin-bottom: 24px; line-height: 1.8; color: #666; font-size: 14px; font-style: italic;">* 備註文字</p>
   * 如果備註緊接在列表（ul）後面，為了拉開距離，請將 margin-top 改為 24px：
     <p style="margin-top: 24px; margin-bottom: 24px; line-height: 1.8; color: #666; font-size: 14px; font-style: italic;">

6. 【無序列表 (ul)】
   <ul style="margin-top: 0; margin-bottom: 24px; padding-left: 24px; list-style-type: disc;">

7. 【列表項目 (li)】
   - 普通列表項目：
     <li style="margin-bottom: 12px; line-height: 1.6; color: #444;">項目文字</li>
     * 項目內若有粗體字，請用：<strong style="color: #000; font-weight: bold;">粗體文字</strong>

   - 複雜列表項目（有標題 + 說明）：
     <li style="margin-bottom: 16px; line-height: 1.6; color: #444;">
       <strong style="color: #000; font-weight: bold; font-size: 16px; display: block; margin-bottom: 4px;">項目標題</strong>
       <span style="color: #666; font-size: 15px;">項目詳細說明文字</span>
     </li>

---

### 📥 業務規則：
- 嚴禁加入原文冇出現過嘅產品資訊（spec、價錢、評語等都唔可以憑空生成）
- 嚴禁加入規格表 / 配置表 / 技術參數表（spec table 另外處理）
- 輸出語言必須同「詳細描述 HTML」嘅語言一致。英文就全英文、中文就全中文，唔好混合語言。

---

### 產品文案（請直接轉換以下內容）：

**產品名稱**: {product_name}
**產品型號**: {product_model}
**摘要**: {summary}

**詳細描述 HTML**:
{description_html}

---

### 📥 輸出格式要求：
- 請直接輸出完整的 HTML 代碼，放在一個代碼塊（Code Block）中。
- 不要寫任何多餘的解釋，方便我直接複製。
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
) -> str:
    """用 OpenRouter AI 生成 Shopline 兼容嘅帶 inline styles HTML。

    失敗時 return 空 string（graceful fallback）。
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
                return result.strip()
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

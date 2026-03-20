from openai import AsyncOpenAI

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


SHOPLINE_PROMPT = """你係一個 Shopline 商品描述 HTML 生成器。你嘅工作係將產品資料轉換為一段精美嘅、帶 inline styles 嘅 HTML，可以直接貼入 Shopline 商品描述編輯器。

## 產品資料

**產品名稱**: {product_name}
**產品型號**: {product_model}
**摘要**: {summary}

**詳細描述 HTML**:
{description_html}

## 輸出要求

1. **全部用 inline styles** — Shopline 唔支援 <style> 標籤或外部 CSS，所有 styling 必須用 style="" attribute
2. **響應式 layout** — 用 flex-wrap、min-width、max-width: 100% 確保手機都排得靚
3. **中文字體 stack** — font-family: 'PingFang TC', 'Heiti TC', 'Microsoft JhengHei', 'Noto Sans TC', sans-serif
4. **標準結構**（按順序）：
   - Hero banner：產品名 + 摘要，深色背景（#1a1a2e 或類似），白字，大字體
   - 核心優勢 cards：用 flex-wrap layout，每個 card 有 icon（emoji）+ 標題 + 簡短描述
   - 詳細介紹 sections：將描述內容分段展示，每段有標題
5. **用 emoji 做 icon**（⚡🌐📡💎✔🔒🖥️📊🎯🔧💡🚀等），唔好用圖片
6. **Section headings** 用藍色左邊 accent bar（border-left: 4px solid #2563eb; padding-left: 12px）
7. **配色方案**：專業科技風格，主色 #2563eb（藍），深色背景 #1a1a2e，淺色區域 #f8f9fa
8. **嚴禁加入原文冇出現嘅產品資訊**（可以重新組織排版，但內容必須來自輸入資料）
9. **唔好用 markdown code block 包裹輸出** — 直接輸出 HTML

直接回傳完整嘅 HTML 代碼，唔好加任何解釋。
"""

DEFAULT_MODEL = "google/gemini-3-flash-preview"


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
    except Exception:
        return ""

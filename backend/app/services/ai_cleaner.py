from openai import AsyncOpenAI


CLEAN_PROMPT = """你係一個商品描述編輯器。以下係從「{product_name}」產品頁面提取嘅 HTML 內容。

請執行以下工作：
1. 移除重複內容（同一段描述出現多次）
2. 移除非商品描述嘅內容（導航、免責聲明、版權、cookie 提示等）
3. 保留所有有用嘅商品特色、功能描述、規格重點
4. 保持 HTML 標籤格式（h2/h3/h4, p, ul/ol/li, table, strong/em）
5. 唔好加任何新內容，只做篩選同去重

直接回傳清理後嘅 HTML，唔好加任何解釋。

---
{raw_html}
"""

DEFAULT_MODEL = "google/gemini-3-flash-preview"


async def clean_description_with_ai(
    raw_html: str,
    product_name: str,
    api_key: str,
    model: str | None = None,
) -> str:
    """用 OpenRouter AI 清理 description_html，移除重複/無關內容。

    如果 AI call 失敗，return 原本嘅 raw_html（graceful fallback）。
    """
    try:
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        response = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": CLEAN_PROMPT.format(
                        product_name=product_name,
                        raw_html=raw_html,
                    ),
                }
            ],
        )
        cleaned = response.choices[0].message.content
        if cleaned:
            return cleaned
        return raw_html
    except Exception:
        return raw_html

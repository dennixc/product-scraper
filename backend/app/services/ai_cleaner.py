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


CLEAN_PROMPT = """你係一個商品描述篩選器。以下係從「{product_name}」產品頁面提取嘅 HTML 內容。

你嘅唯一工作係「刪除無用嘅段落/句子」，絕對唔可以改動保留嘅文字。

規則：
1. 移除重複內容（同一段描述出現多次，只保留一次）
2. 移除非商品描述嘅內容（導航、免責聲明、版權、cookie 提示等）
3. 保留所有有用嘅商品特色、功能描述、規格重點
4. 保持 HTML 標籤格式（h2/h3/h4, p, ul/ol/li, table, strong/em）

嚴禁事項（違反任何一條即為失敗）：
- 嚴禁加入任何原文冇出現過嘅字詞
- 嚴禁改寫、paraphrase、或重新組織句子
- 嚴禁翻譯（例如將中文變英文、或英文變中文）
- 嚴禁修改標點符號或空格
- 保留嘅文字必須同原文逐字一致

你只可以做一件事：決定每個段落/句子「保留」定「刪除」。保留嘅內容必須原封不動。

直接回傳清理後嘅 HTML，唔好加任何解釋或 markdown code block。

---
{raw_html}
"""

DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324"


def _build_cleaner_hints(analysis: dict | None) -> str:
    if not analysis:
        return ""
    if analysis.get("content_language"):
        return f"\n\n注意：內容主要語言係 {analysis['content_language']}，呢個語言嘅內容都係有用嘅，唔好因為語言而移除。"
    return ""


async def clean_description_with_ai(
    raw_html: str,
    product_name: str,
    api_key: str,
    model: str | None = None,
    analysis: dict | None = None,
) -> str:
    """用 OpenRouter AI 清理 description_html，移除重複/無關內容。

    如果 AI call 失敗，return 原本嘅 raw_html（graceful fallback）。
    """
    try:
        prompt_text = CLEAN_PROMPT.format(
            product_name=product_name,
            raw_html=_truncate_html(raw_html),
        )
        prompt_text += _build_cleaner_hints(analysis)

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
                    "content": prompt_text,
                }
            ],
        )
        cleaned = response.choices[0].message.content
        if cleaned:
            return cleaned
        return raw_html
    except Exception:
        return raw_html

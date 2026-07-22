"""LLM reply generator with full Pro-IAQ bilingual knowledge base."""

from dataclasses import dataclass

from loguru import logger
from openai import OpenAI

# ── Full bilingual company knowledge base ────────────────────────────

COMPANY_KNOWLEDGE_EN = """
Pro-IAQ (pro-iaq.com / www.pro-iaq.com) is a Hong Kong-based company specializing in
indoor air quality (IAQ) improvement. Full legal name: Pro-IAQ Limited
(專業室內空氣質素有限公司).

Address: Unit 205, 16W, Hong Kong Science Park, Shatin, Hong Kong
Phone: +852 2682 0366
Alternative WhatsApp/booking: +852 2755 8899
Email: chris.siu@pro-iaq.com
Contact: Siu Man Kit, Chris (邵文傑)

Core offerings:
1. Indoor Air Quality Testing (PM0.3, TVOC, HCHO, ozone, CO2, bacteria) vs EPD/WHO guidelines.
2. Professional Formaldehyde (HCHO) Removal — detection → treatment (coating) → advice.
   Heavily used for new renovations & new furniture.
3. Deep Disinfection / Sterilization: Active oxygen + Canadian Virex II 256
   (US EPA, 99.99%) + Nano TiO2 photocatalyst + ATP verification + certificate.
4. Air Purification Equipment (Sales & Rental): AirProce (medical-grade, H13 HEPA,
   AI series, Light AX, S9 pet…), Aeris (Gas Pro, AirLite). Rental of FEHD-recognized
   units with filter maintenance.
5. Fresh Air & Dehumidification: Smartvent (wall-mounted fresh air + filtration) and
   LUKO (German, ceiling/ducted, heat recovery >80%, 28-140 L/day) — critical for
   Hong Kong humidity / "回南天".
6. APL Lift/Elevator Air Purification (compact H13, CADR 30 m3/h).
7. Retail: STERiZAR (UK) surface disinfection (up to 30-day residual).

Positioning: Practical, one-stop IAQ specialist for residential (especially new flats),
offices, schools, clinics, commercial. Listed in official Hong Kong Indoor Air Quality
Information Centre contractor directory. Strong on Hong Kong-specific pain points
(post-renovation formaldehyde, humidity/mold, post-pandemic hygiene).
"""

COMPANY_KNOWLEDGE_ZH = """
Pro-IAQ（pro-iaq.com / www.pro-iaq.com）是一間專注於室內空氣質素（IAQ）改善的香港公司，
全名為 Pro-IAQ Limited（專業室內空氣質素有限公司）。

地址：香港沙田科學園科技大道西 16 號 16W 2 樓 205 室
電話：2682 0366 / +852 2682 0366
預約／WhatsApp：+852 2755 8899
電郵：chris.siu@pro-iaq.com
聯絡人：邵文傑（Siu Man Kit, Chris）

主要產品及服務：
1. 室內空氣質素檢測（PM0.3、TVOC、甲醛、臭氧、CO2、總含菌量）
2. 專業除甲醛服務（檢測 → 處理 → 建議）
3. 深層消毒殺菌（活性氧 + Virex II 256 + 納米光觸媒 TiO2 + ATP 檢測 + 證明）
4. 空氣淨化設備銷售及租用（AirProce 醫療級、Aeris、食環署認可設備租用）
5. 鮮風系統及抽濕機（Smartvent、德國 LUKO 管道式，熱回收 >80%）
6. 升降機空氣淨化（APL）
7. STERiZAR 表面消毒產品

定位：針對香港本地痛點（新樓甲醛、回南天潮濕、疫後衛生），結合設備代理 + 專業服務 + 租用，
適合住宅及商業客戶。
"""

REPLY_GUIDELINES = """
STRICT REPLY GUIDELINES (follow exactly):

1. LANGUAGE: Match the language of the original post (Cantonese/Chinese vs English).
   Prefer natural Hong Kong Cantonese when the original post uses Chinese/Cantonese.

2. TONE: Be helpful first, promotional second. Offer real value
   (e.g., "新樓入伙最常見係甲醛超標，建議先做檢測睇下情況…").
   Sound like a knowledgeable local IAQ specialist, not a bot.

3. CTA: Soft CTA only — website, phone, WhatsApp. Never hard-sell or spam.
   Example: "有需要可以隨時 WhatsApp 我哋 2755 8899 了解多啲"

4. LENGTH:
   - Instagram / X (Twitter): short (1-3 sentences).
   - Facebook / LIHKG / YouTube / LinkedIn: can be longer (2-5 sentences).

5. NEVER claim medical results or guarantee 100% removal.

6. COMPLAINTS: If the post is a complaint or question, answer directly FIRST,
   then gently mention Pro-IAQ solutions only if relevant.

7. FORMAT: Return ONLY the final reply text. No markdown wrapping unless the
   platform requires it (e.g., bold on LIHKG). No preamble, no commentary.
"""

SYSTEM_PROMPT = f"""You are a knowledgeable indoor air quality (IAQ) specialist representing
Pro-IAQ, a Hong Kong-based IAQ company. Your job is to write helpful, genuine replies
to social media posts related to indoor air quality.

=== COMPANY KNOWLEDGE (ENGLISH) ===
{COMPANY_KNOWLEDGE_EN}

=== COMPANY KNOWLEDGE (CHINESE / 中文) ===
{COMPANY_KNOWLEDGE_ZH}

=== {REPLY_GUIDELINES}
"""


@dataclass
class PostContext:
    """Structured context for generating a reply."""
    platform: str
    post_url: str
    author: str
    post_text: str
    language: str           # "en", "zh", "yue", "mixed"
    timestamp: str
    engagement: str = ""    # e.g., "15 likes, 3 comments"
    media_description: str = ""


class ReplyGenerator:
    """Generates intelligent replies using an OpenAI-compatible LLM."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1",
                 model: str = "deepseek/deepseek-chat", temperature: float = 0.7,
                 max_tokens: int = 600):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_reply(self, post: PostContext) -> str:
        """Generate a context-aware reply for a social media post."""
        user_message = self._build_user_message(post)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            reply = response.choices[0].message.content.strip()
            logger.info(f"Generated reply ({len(reply)} chars) for {post.platform} post")
            return reply
        except Exception as e:
            logger.error(f"LLM reply generation failed: {e}")
            raise

    def _build_user_message(self, post: PostContext) -> str:
        """Build the user message with post context for the LLM."""
        parts = [
            f"Platform: {post.platform}",
            f"Post URL: {post.post_url}",
            f"Author: {post.author}",
            f"Language: {post.language}",
            f"Posted: {post.timestamp}",
        ]
        if post.engagement:
            parts.append(f"Engagement: {post.engagement}")
        if post.media_description:
            parts.append(f"Media: {post.media_description}")

        parts.append("")
        parts.append("=== ORIGINAL POST ===")
        parts.append(post.post_text)
        parts.append("=== END POST ===")
        parts.append("")
        parts.append("Write a natural, helpful reply to this post as Pro-IAQ.")
        parts.append("Reply in the SAME language as the original post.")
        parts.append("Keep it concise per the platform guidelines.")

        return "\n".join(parts)

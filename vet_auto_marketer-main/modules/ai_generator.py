"""AI generation layer — wraps Groq (Llama) for captions, replies, trend analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from groq import Groq
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import prompts
from config.settings import settings


_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY missing in .env")
        _client = Groq(api_key=settings.groq_api_key)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _complete(
    system: str,
    user: str,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """Low-level call to Groq. Returns the full text response."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = resp.choices[0].message.content if resp.choices else ""
    return (content or "").strip()


# =============================================================
# High-level helpers
# =============================================================
def translate_edit_instruction(arabic_instruction: str) -> str:
    """Convert a short Arabic edit instruction into a professional English
    image-edit prompt optimized for Nano Banana image-to-image generation.
    """
    system = (
        "You are an expert AI image-editing prompt engineer. "
        "You receive short, casual Arabic instructions from a non-technical user "
        "and rewrite them as precise, professional English edit prompts for an "
        "image-to-image model (Nano Banana). "
        "Output ONLY the final English prompt — no preamble, no quotes, no explanation. "
        "Keep it under 80 words. Be concrete about visual changes (colors, style, "
        "composition, lighting, mood). Preserve the original subject unless asked to replace it. "
        "Never request text or typography in the output."
    )
    user = f"Arabic instruction from the user:\n{arabic_instruction}\n\nRewrite as an English edit prompt:"
    try:
        out = _complete(system=system, user=user, max_tokens=250, temperature=0.5)
        return out.strip().strip('"').strip("'")
    except Exception as e:
        logger.exception("translate_edit_instruction failed: {}", e)
        return arabic_instruction


def generate_caption(
    content_type: str,
    media_description: str,
    goal: str = "توعية",
) -> str:
    """Generate an Instagram caption for the given media description."""
    user_prompt = prompts.CAPTION_PROMPT.format(
        clinic_identity=prompts.CLINIC_IDENTITY,
        content_type=content_type,
        media_description=media_description,
        goal=goal,
    )
    try:
        return _complete(
            system="You are a senior Arabic social media copywriter.",
            user=user_prompt,
            max_tokens=900,
            temperature=0.8,
        )
    except Exception as e:
        logger.exception("generate_caption failed: {}", e)
        return ""


def generate_dm_reply(
    customer_message: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    if prompts.is_emergency(customer_message):
        return prompts.EMERGENCY_AUTO_REPLY

    history_text = ""
    if conversation_history:
        lines = []
        for m in conversation_history[-10:]:
            role = m.get("role", "user")
            text = m.get("text", "")
            lines.append(f"{role}: {text}")
        history_text = "\n".join(lines)

    user_prompt = prompts.DM_REPLY_PROMPT.format(
        clinic_identity=prompts.CLINIC_IDENTITY,
        customer_message=customer_message,
        conversation_history=history_text or "(لا توجد محادثة سابقة)",
        clinic_phone=settings.clinic_phone,
    )
    try:
        return _complete(
            system="You are a warm, human-sounding customer-service agent replying in Iraqi Arabic.",
            user=user_prompt,
            max_tokens=400,
            temperature=0.7,
        )
    except Exception as e:
        logger.exception("generate_dm_reply failed: {}", e)
        return ""


def generate_comment_reply(
    post_description: str,
    comment_text: str,
    commenter_name: str,
) -> str:
    user_prompt = prompts.COMMENT_REPLY_PROMPT.format(
        clinic_identity=prompts.CLINIC_IDENTITY,
        post_description=post_description,
        comment_text=comment_text,
        commenter_name=commenter_name,
    )
    try:
        return _complete(
            system="Short Iraqi-Arabic Instagram comment replies.",
            user=user_prompt,
            max_tokens=200,
            temperature=0.8,
        )
    except Exception as e:
        logger.exception("generate_comment_reply failed: {}", e)
        return ""


def generate_dm_to_commenter(
    post_description: str,
    comment_text: str,
    commenter_name: str,
) -> str:
    user_prompt = prompts.DM_TO_COMMENTER_PROMPT.format(
        clinic_identity=prompts.CLINIC_IDENTITY,
        post_description=post_description,
        comment_text=comment_text,
        commenter_name=commenter_name,
    )
    try:
        return _complete(
            system="Follow-up DM in Iraqi Arabic — warm, brief, non-salesy.",
            user=user_prompt,
            max_tokens=350,
            temperature=0.75,
        )
    except Exception as e:
        logger.exception("generate_dm_to_commenter failed: {}", e)
        return ""


@dataclass
class TrendAnalysis:
    relevant: bool
    caption: str
    content_type: str  # Post | Story | Reel
    urgency: str       # High | Medium | Low
    reason: str


def analyze_trend(
    trend_topic: str,
    trend_volume: int | str,
    trend_type: str = "general",
) -> TrendAnalysis:
    user_prompt = prompts.TREND_CONTENT_PROMPT.format(
        clinic_identity=prompts.CLINIC_IDENTITY,
        trend_topic=trend_topic,
        trend_volume=trend_volume,
        trend_type=trend_type,
    )
    try:
        raw = _complete(
            system="Trend analyst for a vet clinic. Be strict about relevance.",
            user=user_prompt,
            max_tokens=700,
            temperature=0.6,
        )
    except Exception as e:
        logger.exception("analyze_trend failed: {}", e)
        return TrendAnalysis(False, "", "Post", "Low", f"error: {e}")

    return _parse_trend_output(raw)


def _parse_trend_output(raw: str) -> TrendAnalysis:
    """Parse the structured response from the trend prompt."""
    fields = {"RELEVANCE": "", "CAPTION": "", "CONTENT_TYPE": "",
              "URGENCY": "", "REASON": ""}
    current_key: Optional[str] = None
    buf: Dict[str, List[str]] = {k: [] for k in fields}
    for line in (raw or "").splitlines():
        stripped = line.strip()
        matched = False
        for key in fields:
            if stripped.upper().startswith(f"{key}:"):
                current_key = key
                value = stripped.split(":", 1)[1].strip()
                buf[key].append(value)
                matched = True
                break
        if not matched and current_key:
            buf[current_key].append(stripped)

    for k in fields:
        fields[k] = "\n".join(x for x in buf[k] if x).strip()

    relevant = fields["RELEVANCE"].upper().startswith("Y")
    return TrendAnalysis(
        relevant=relevant,
        caption=fields["CAPTION"] if fields["CAPTION"] != "-" else "",
        content_type=fields["CONTENT_TYPE"] or "Post",
        urgency=fields["URGENCY"] or "Low",
        reason=fields["REASON"] or "",
    )


# =============================================================
# Manual smoke test
# =============================================================
if __name__ == "__main__":
    logger.info("Testing caption generation…")
    print(generate_caption(
        content_type="Post",
        media_description="صورة قطة بيضاء صغيرة عندها التهاب في عينها",
        goal="توعية",
    ))

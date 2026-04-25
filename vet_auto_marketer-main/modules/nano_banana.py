"""
Nano Banana API integration — V2 (Generate-2)
يولّد صور AI بالهوية البصرية لعيادة الكوخ
API Docs: https://docs.nanobananaapi.ai

تدفق العمل (async):
    1. POST /api/v1/nanobanana/generate-2   →  يرجّع taskId  (8 credits/call @ 1K)
    2. GET  /api/v1/nanobanana/record-info?taskId=...  →  polling لحد ما تكتمل
"""

import time
import requests
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import settings


API_BASE = "https://api.nanobananaapi.ai"
SUBMIT_URL = f"{API_BASE}/api/v1/nanobanana/generate-2"  # V2 endpoint (8 credits/call, 1K)
POLL_URL = f"{API_BASE}/api/v1/nanobanana/record-info"

POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 180

# =============================================================
# Brand Style Presets — الصورة تحمل رسالتها بداخلها
# =============================================================

BRAND_STYLE_INFOGRAPHIC = """
STYLE: Premium social media infographic design for ALKOUKH Veterinary Clinic (عيادة الكوخ).
Brand colors: Royal purple (#7B2FBE) and Magenta-Pink (#D946EF) with white text.
Composition: Professional graphic design layout — NOT a photograph.
Layout: The image itself is the complete message:
  - Large bold Arabic text as the MAIN HEADLINE at the top or center (make it read clearly).
  - A beautiful photorealistic illustration or photo of a cute pet (cat or dog) integrated into the layout.
  - Supporting visual icons or graphical elements that reinforce the message.
  - Clinic brand name "الكوخ" in a stylish subtle corner watermark.
  - Gradient purple-to-magenta background with glassmorphism card elements.
Requirement: The Arabic text inside the image MUST be legible, large, and be the focal point.
Output: A complete, standalone social media post — no caption needed to understand it.
"""

BRAND_STYLE_POSTER = """
STYLE: Professional Arabic social media poster / educational card.
Brand: ALKOUKH Veterinary Clinic (الكوخ) — Iraq's premium vet brand.
Color palette: Deep purple (#7B2FBE), Magenta (#D946EF), clean white backgrounds for text sections.
Layout structure:
  - TOP: Clinic logo area / brand name with small paw icon
  - CENTER: Large, bold Arabic text title — the MAIN message or tip
  - MIDDLE VISUAL: A stunning high-quality photo of a pet (cat/dog/rabbit) embedded as a circle or card
  - BOTTOM: 2-3 short bullet points OR a key fact — written in Arabic
  - FOOTER: Subtle gradient band with clinic name
Aesthetic: Modern, clean, Instagram-worthy. Inspired by top-tier Arab veterinary social accounts.
Requirement: ALL Arabic text in the image must be sharp, bold, and clearly readable.
"""

STORY_STYLE = """
Instagram Story for ALKOUKH Veterinary Clinic — 9:16 vertical format.
Design style: Premium Arabic educational story card.
Layout (top to bottom):
  - TOP SECTION (25%): Clinic name header "عيادة الكوخ" on purple gradient band
  - MAIN VISUAL (40%): Beautiful pet photo (cat or dog) with rounded corners — real photographic quality
  - MIDDLE TEXT (20%): Large bold Arabic headline — the main tip or message — white text on purple card
  - BOTTOM (15%): Short CTA or sub-text in Arabic + small paw icon
Color: Purple (#7B2FBE) to Magenta (#D946EF) gradient background throughout.
Arabic text must be LARGE, BOLD, and the primary focal point of the story.
The image must be self-explanatory — no external caption needed.
"""

VET_TIP_TOPICS = [
    "أشياء لازم تعلمها لطفلك قبل ما يربي حيوان أليف",
    "كيف تعرف إذا قطتك مريضة — ٥ علامات خطيرة",
    "التطعيمات الأساسية للجراء الصغيرة في العراق",
    "أخطاء شائعة بتغذية القطط المنزلية",
    "ليش الفحص الدوري البيطري مهم حتى لو حيوانك يبين بخير",
    "أول يوم تجيب قطة للبيت — شنو تسوي وشنو تتجنب",
    "الحر والصيف — كيف تحمي حيوانك الأليف بالعراق",
    "الأكل الممنوع للكلاب — قائمة لازم كل مربي يعرفها",
    "علامات التوتر والقلق عند القطط وكيف تهديها",
    "كيف تختار الطبيب البيطري المناسب لحيوانك",
    "العناية بأسنان الحيوانات الأليفة — أهم شي ينتسى",
    "متى تحتاج تاخذ حيوانك للطوارئ فوراً",
    "تربية الأرانب بالبيت — نصائح من عيادة الكوخ",
    "البراغيث والقراد — الوقاية أسهل من العلاج",
    "كيف تعوّد حيوانك على الشنطة والسفر",
]

# مواضيع يوميات العيادة
DAILY_LIFE_THEMES = [
    "يوم عادي بعيادة الكوخ — الفحوصات اليومية",
    "لحظة لطيفة — حيوان خايف بأول زيارة",
    "فريق عمل عيادة الكوخ بالعمل",
    "عملية ناجحة — ابتسامة الطبيب بعد الجراحة",
    "تطعيم القطط الصغيرة — روتين يومي",
    "ضيف جديد بالعيادة — أول فحص للجرو",
    "المختبر البيطري — فحوصات الدم والتحاليل",
    "لحظات مؤثرة — صاحب الحيوان يستلم حيوانه بعد العلاج",
]

# مواضيع عاطفية
EMOTIONAL_THEMES = [
    "الحيوانات تحس بينا — لحظات حب بين الحيوان وصاحبه",
    "عيون الأمل — حيوان بعد العلاج يرجع يلعب",
    "الحب اللي مايخون — الوفاء بين الحيوان والإنسان",
    "أول مرة يمسك طفل حيوان أليف",
    "قصة نجاح — من المرض للشفاء",
    "لحظة وداع مؤثرة — الطبيب البيطري والحالات الصعبة",
]

# مواضيع خدمات العيادة
SERVICE_TOPICS = [
    "خدمة التطعيمات واللقاحات",
    "المختبر المتطور — فحوصات شاملة",
    "العمليات الجراحية المتقدمة",
    "خدمة الطوارئ البيطرية",
    "العناية بالأسنان والفم",
    "فحص صحي شامل لحيوانك",
    "خدمة الاستشارة عن بعد",
    "علاج الأمراض الجلدية",
]


class NanaBananaService:
    def __init__(self):
        self.api_key = settings.nano_banana_api_key
        self.output_dir = settings.nano_banana_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_error: str | None = None

    def _friendly_error(self, exc: Exception) -> str:
        # Unwrap tenacity RetryError to get the real cause
        root = exc
        while hasattr(root, "last_attempt") and root.last_attempt is not None:
            try:
                root = root.last_attempt.exception() or root
                break
            except Exception:
                break
        if getattr(exc, "__cause__", None):
            root = exc.__cause__
        msg = str(root)
        low = msg.lower()
        if "insufficient" in low or "402" in msg or "top up" in low:
            return "⚠️ رصيد Nano Banana خلص — لازم تشحن الحساب من nanobananaapi.ai/dashboard"
        if "401" in msg or "unauthorized" in low:
            return "⚠️ Nano Banana API key غير صحيح أو منتهي"
        if "timeout" in low:
            return "⚠️ Nano Banana بطيء اليوم — حاول مرة ثانية"
        return f"فشل التوليد: {msg[:250]}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_random_style(self) -> str:
        import random
        return random.choice([BRAND_STYLE_INFOGRAPHIC, BRAND_STYLE_POSTER])

    def _build_prompt(self, description: str, aspect: str, style_override: str | None = None) -> str:
        style = style_override or self._get_random_style()
        ratio_hint = "square 1:1 format" if aspect == "1:1" else "vertical 9:16 story format"
        return f"Social media content design: {description}. | {style} | Format: {ratio_hint}. | The Arabic text inside the image is MANDATORY and must be large, bold, and clearly legible."

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _submit(self, prompt: str, aspect_ratio: str, image_urls: list[str] | None = None) -> str:
        """Submit to Nano Banana V2 (Generate-2) endpoint — 8 credits/call, 1K resolution."""
        if not self.api_key:
            raise RuntimeError("NANO_BANANA_API_KEY not set in .env")

        # V2 payload format (different from V1)
        payload: dict = {
            "prompt": prompt,
            "imageUrls": image_urls or [],
            "aspectRatio": aspect_ratio,   # e.g. "1:1", "9:16", "auto"
            "resolution": "1K",             # 1K = 8 credits | 2K = 12 | 4K = 18
            "googleSearch": False,
            "outputFormat": "jpg",
            "callBackUrl": "https://example.com/noop",
        }
        logger.info("Submitting Nano Banana V2 task ({}, mode={}, res=1K)",
                    aspect_ratio, "edit" if image_urls else "text-to-image")
        r = requests.post(SUBMIT_URL, headers=self._headers(), json=payload, timeout=60)
        if r.status_code != 200:
            logger.error("Nano Banana V2 submit failed ({}): {}", r.status_code, r.text)
            r.raise_for_status()

        body = r.json()
        if body.get("code") != 200:
            raise RuntimeError(f"Nano Banana V2 rejected task: {body}")

        task_id = (body.get("data") or {}).get("taskId")
        if not task_id:
            raise RuntimeError(f"No taskId in V2 submit response: {body}")
        return task_id

    def _poll(self, task_id: str, timeout_s: int = POLL_TIMEOUT_S) -> str:
        deadline = time.time() + timeout_s
        last_flag = None
        while time.time() < deadline:
            r = requests.get(
                POLL_URL,
                params={"taskId": task_id},
                headers=self._headers(),
                timeout=30,
            )
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}
            flag = data.get("successFlag")

            if flag == 1:
                url = (data.get("response") or {}).get("resultImageUrl")
                if not url:
                    raise RuntimeError(f"Task succeeded but no resultImageUrl: {data}")
                return url

            if flag in (2, 3):
                msg = data.get("errorMessage") or "unknown error"
                raise RuntimeError(f"Nano Banana generation failed: {msg}")

            if flag != last_flag:
                logger.debug("Polling task {} — status={}", task_id, flag)
                last_flag = flag
            time.sleep(POLL_INTERVAL_S)

        raise TimeoutError(f"Nano Banana task {task_id} did not finish in {timeout_s}s")

    def _call_api(self, prompt: str, aspect_ratio: str = "1:1",
                  image_urls: list[str] | None = None) -> str:
        """Submit + poll. Returns the final image URL."""
        task_id = self._submit(prompt, aspect_ratio, image_urls=image_urls)
        logger.info("Nano Banana task submitted: {}", task_id)
        url = self._poll(task_id)
        logger.success("Nano Banana task {} completed", task_id)
        return url

    def _download_image(self, url: str, filename: str) -> Path:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        out_path = self.output_dir / filename
        out_path.write_bytes(response.content)
        logger.info("Image saved: {}", out_path)
        return out_path

    def _apply_format(self, prompt: str, content_format: str) -> tuple[str, str]:
        aspect_ratio = "9:16" if content_format == "story" else "1:1"
        if content_format == "story":
            prompt += " " + STORY_STYLE.replace("\n", " ")
        return prompt, aspect_ratio

    def generate_tip_image(self, topic: str, content_format: str = "post") -> Path | None:
        """يولّد بوستر نصيحة بيطرية — الصورة تحمل النصيحة كاملة بداخلها"""
        try:
            base_prompt = (
                f"Create a complete Arabic veterinary tip infographic. "
                f"The MAIN HEADLINE in Arabic at the top: bold, large, readable — about: '{topic}'. "
                f"Include 2-3 bullet points written in Arabic inside the design explaining the tip clearly. "
                f"A beautiful high-quality photo of a cute cat or dog integrated as a visual element. "
                f"Design should feel complete and self-explanatory — a person reading only the image understands the full tip. "
                f"Clinic name 'الكوخ' in small watermark. Brand colors: purple #7B2FBE and magenta #D946EF."
            )
            prompt, aspect_ratio = self._apply_format(base_prompt, content_format)
            prompt = self._build_prompt(prompt, aspect_ratio)
            url = self._call_api(prompt, aspect_ratio)
            return self._download_image(url, f"tip_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("generate_tip_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def generate_trend_image(self, trend: str, caption_hint: str = "", content_format: str = "post") -> Path | None:
        """يولّد بوستر ترند بيطري مع نص الرسالة مدمج بالصورة"""
        try:
            base_prompt = (
                f"Create an Arabic social media post connecting the viral trend '{trend}' to veterinary care. "
                f"LARGE bold Arabic text inside the image showing a clever, witty headline that links the trend to pet health. "
                f"{('Context: ' + caption_hint[:100]) if caption_hint else ''} "
                f"An eye-catching, Instagram-worthy composition. "
                f"A photogenic cat or dog featured prominently as the visual hook. "
                f"Purple (#7B2FBE) and magenta (#D946EF) brand colors. Clinic name 'الكوخ' visible."
            )
            prompt, aspect_ratio = self._apply_format(base_prompt, content_format)
            prompt = self._build_prompt(prompt, aspect_ratio)
            url = self._call_api(prompt, aspect_ratio)
            return self._download_image(url, f"trend_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("generate_trend_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def generate_daily_life_image(self, theme: str, content_format: str = "post") -> Path | None:
        """يولّد بوستر يوميات العيادة — مشهد واقعي مع عنوان واضح مدمج بالصورة"""
        try:
            base_prompt = (
                f"Create a behind-the-scenes clinic social media post: '{theme}'. "
                f"LARGE Arabic text headline integrated into the image design, describing the scene or a warm human message. "
                f"Photorealistic scene of a modern veterinary clinic: vet staff, cute pets, professional equipment. "
                f"Warm and authentic feel — like a premium Instagram clinic account. "
                f"Purple/lavender tones. Clinic name 'الكوخ' subtly visible in the scene or as overlay."
            )
            prompt, aspect_ratio = self._apply_format(base_prompt, content_format)
            prompt = self._build_prompt(prompt, aspect_ratio)
            url = self._call_api(prompt, aspect_ratio)
            return self._download_image(url, f"daily_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("generate_daily_life_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def generate_emotional_image(self, theme: str, content_format: str = "post") -> Path | None:
        """يولّد بوستر عاطفي — الصورة تنقل المشاعر والرسالة بشكل متكامل"""
        try:
            base_prompt = (
                f"Create a deeply emotional Arabic social media post: '{theme}'. "
                f"LARGE, evocative Arabic quote or headline embedded inside the image — the emotional message in bold. "
                f"A heartwarming cinematic scene: a pet and its owner or a vet caring for an animal. "
                f"Soft, emotional lighting — cinematic quality. "
                f"The image should make someone stop scrolling and feel something. "
                f"Subtle lavender and purple tones. Clinic name 'الكوخ' as a gentle watermark."
            )
            prompt, aspect_ratio = self._apply_format(base_prompt, content_format)
            prompt = self._build_prompt(prompt, aspect_ratio)
            url = self._call_api(prompt, aspect_ratio)
            return self._download_image(url, f"emotional_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("generate_emotional_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def generate_service_image(self, service: str, content_format: str = "post") -> Path | None:
        """يولّد بوستر خدمة بيطرية — إعلان احترافي مع كل المعلومات بالصورة"""
        try:
            base_prompt = (
                f"Create a professional Arabic service advertisement for a veterinary clinic. Service: '{service}'. "
                f"LARGE bold Arabic title of the service at the top of the image. "
                f"Key benefits or features of the service written as 2-3 short Arabic bullet points inside the design. "
                f"A professional veterinarian photo or a pet being cared for as the hero visual. "
                f"Clean medical aesthetic: modern clinic, professional purple (#7B2FBE) and white color scheme. "
                f"Clinic name 'الكوخ' prominently visible. CTA like 'احجز الآن' or 'تواصل معنا' in Arabic at bottom."
            )
            prompt, aspect_ratio = self._apply_format(base_prompt, content_format)
            prompt = self._build_prompt(prompt, aspect_ratio)
            url = self._call_api(prompt, aspect_ratio)
            return self._download_image(url, f"service_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("generate_service_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def edit_image(self, image_url: str, english_prompt: str,
                   aspect_ratio: str = "1:1") -> Path | None:
        """Image-to-image edit. `image_url` must be publicly accessible.
        `english_prompt` should already be a professional edit instruction in English.
        """
        try:
            full_prompt = (
                f"{english_prompt}. "
                "Preserve the core subject and composition of the original image. "
                "Apply the edit cleanly. Do NOT add any text, letters, or typography."
            )
            url = self._call_api(full_prompt, aspect_ratio, image_urls=[image_url])
            return self._download_image(url, f"edit_{int(time.time())}.jpg")
        except Exception as e:
            logger.exception("edit_image failed: {}", e)
            self.last_error = self._friendly_error(e)
            return None

    def batch_generate_daily_tips(self, count: int = 5) -> list[Path]:
        import random
        topics = random.sample(VET_TIP_TOPICS, min(count, len(VET_TIP_TOPICS)))
        results = []
        for topic in topics:
            path = self.generate_tip_image(topic)
            if path:
                results.append(path)
                time.sleep(2)
        logger.success("Generated {}/{} daily tip images", len(results), count)
        return results


    def generate_varied_content(self, content_format: str = "post") -> Path | None:
        """يولّد محتوى متنوع (نصيحة، عاطفي، أو ترند) بأسلوب عشوائي"""
        import random
        from database import content_queue as cq
        
        # Get latest trend if available for trend content
        latest_trend = None
        trends = cq.list_trends_today(limit=1)
        if trends:
            latest_trend = trends[0].get("trend_topic")

        choices = ["tip", "emotional"]
        if latest_trend:
            choices.append("trend")
            
        choice = random.choice(choices)
        logger.info("Auto-generating Nano Banana content: choice={}", choice)
        
        if choice == "tip":
            return self.generate_tip_image(random.choice(VET_TIP_TOPICS), content_format)
        elif choice == "emotional":
            return self.generate_emotional_image(random.choice(EMOTIONAL_THEMES), content_format)
        elif choice == "trend" and latest_trend:
            return self.generate_trend_image(latest_trend, content_format=content_format)
        
        # Fallback to tip
        return self.generate_tip_image(random.choice(VET_TIP_TOPICS), content_format)


nano_banana = NanaBananaService()

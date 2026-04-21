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

BRAND_STYLE_REALISTIC = """
STYLE: Masterpiece Photorealistic Photography.
Visual identity: ALKOUKH Veterinary Clinic (الكوخ) — Premium Iraqi veterinary brand.
Composition: Professional studio lighting, shallow depth of field (bokeh), sharp focus on pet's eyes.
Attributes: High-resolution, cinematic lighting, 8k, warm natural tones, professional camera gear (Sony A7R IV).
Branding: Subtle integration of deep royal purple (#7B2FBE) and magenta-pink (#D946EF) in the environment or accessories.
Rules: NO TEXT, NO LETTERS, NO WORDS. healthy, adorable pets only.
"""

FLAT_ILLUSTRATION_STYLE = """
STYLE: Modern Flat 2D Vector Illustration.
Visual identity: ALKOUKH Veterinary Clinic (الكوخ) branding.
Composition: Minimalist, clean bold lines, flat colors, no complex gradients on characters. 
Attributes: Inspired by modern digital vector art, clean SVG-style paths, professional character design.
Character: Friendly tan-skinned Iraqi veterinarian with dark hair, wearing purple scrubs/apron with brand colors.
Branding: Heavy use of royal purple (#7B2FBE), magenta (#D946EF), and lavender accents. 
Mood: Warm, welcoming, and high-tech minimalist.
Rules: NO TEXT, NO LETTERS, NO WORDS.
"""


# ستوريات بأسلوب بولارويد — مكتشف من highlights عيادة الكوخ
STORY_STYLE = """
Instagram Story design matching ALKOUKH Veterinary Clinic (الكوخ) brand:

Layout structure (9:16 vertical):
  - Full-bleed purple/magenta gradient background
  - CENTER: A white Polaroid-style photo frame (slightly tilted 2-3 degrees)
  - Inside the frame: a photorealistic image of a cute pet or clinic scene
  - Below the Polaroid frame: empty space for Arabic text overlay
  - Above the frame: empty space for clinic name text
  - Small hand-drawn heart doodle near the bottom of the Polaroid

Color & mood:
  - Background: rich purple (#7B2FBE) to magenta (#D946EF) gradient
  - Polaroid frame: clean white with subtle shadow
  - Overall mood: warm, friendly, professional, inviting
  - Soft ambient glow around the Polaroid frame

STRICT RULES:
- NO TEXT, NO LETTERS, NO WORDS anywhere in the image.
- NO Arabic or English script. Text will be added separately.
- Pure visual composition only.
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
        return random.choice([BRAND_STYLE_REALISTIC, FLAT_ILLUSTRATION_STYLE])

    def _build_prompt(self, description: str, aspect: str, style_override: str | None = None) -> str:
        style = style_override or self._get_random_style()
        ratio_hint = "square 1:1 format" if aspect == "1:1" else "vertical 9:16 story format"
        return f"Professional vet content: {description}. | {style} | Format: {ratio_hint}."

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
        """يولّد صورة نصيحة بيطرية — بأسلوب احترافي متنوع"""
        try:
            base_prompt = (
                f"Expert-level educational visual for a vet clinic. Subject: '{topic}'. "
                "The composition highlights a specific medical tip or animal care situation. "
                "Main focus: Eye-contact with a healthy pet or an instructional vet demonstration. "
                "Include brand colors purple and magenta in background elements. "
                "The bottom third is reserved for a clean gradient band for caption overlay. "
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
        """يولّد صورة مرتبطة بترند بأسلوب احترافي"""
        try:
            base_prompt = (
                f"A sophisticated clinical visual inspired by the viral trend: '{trend}'. "
                f"Creative context: {caption_hint[:120] if caption_hint else 'trending animal topic'}. "
                "A clever, Instagram-worthy composition that bridges the trend with expert veterinary care. "
                "Vibrant pop of purple and magenta brand colors. Clean focal point. "
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
        """يولّد صورة يوميات العيادة — لقطات من الحياة اليومية"""
        try:
            base_prompt = (
                f"A warm, candid-style photo from inside a veterinary clinic, theme: '{theme}'. "
                "Photorealistic scene showing a modern, clean veterinary clinic interior. "
                "Could include: a veterinarian examining a pet, a pet on an examination table, "
                "medical equipment in the background, staff wearing professional attire. "
                "Warm overhead lighting, slightly desaturated for a natural candid feel. "
                "The scene should feel authentic and documentary-style, like a behind-the-scenes glimpse. "
                "Soft purple/lavender color tones throughout the image. "
                "NO text, no letters, no typography anywhere."
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
        """يولّد صورة عاطفية بأسلوب احترافي يلمس القلب"""
        try:
            base_prompt = (
                f"A cinematic, high-quality emotional masterpiece: '{theme}'. "
                "Heartwarming interaction between a pet and its caretaker. "
                "Deep emotional resonance, soft lighting, evocative composition. "
                "Subtle branding with lavender and soft purple hues. "
                "Premium artistic quality designed for high engagement."
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
        """يولّد صورة خدمة بيطرية — عرض الخدمات باحترافية"""
        try:
            base_prompt = (
                f"Professional veterinary service showcase photo: '{service}'. "
                "A clean, modern veterinary clinic setting showing the service being performed. "
                "Photorealistic: veterinary equipment, examination rooms, lab tools, or surgical suite. "
                "A healthy pet is visible, being cared for by unseen hands (or gentle implied presence). "
                "Clinical but warm aesthetic — modern medical meets compassionate care. "
                "Deep purple (#7B2FBE) and white color scheme throughout the environment. "
                "Bottom 35% has a solid deep purple band for text overlay. "
                "Premium, trust-building imagery. "
                "NO text, no letters, no typography anywhere."
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

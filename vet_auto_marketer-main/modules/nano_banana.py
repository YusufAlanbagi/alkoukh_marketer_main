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
# Style Presets — محايدة، بدون أشخاص، بدون علامات تجارية
# =============================================================

STYLE_INFOGRAPHIC = """
Ultra-premium veterinary social media infographic.
Color palette: Deep royal purple (#7B2FBE), vibrant magenta-pink (#D946EF), pure white.
Composition: Polished graphic design layout with layered depth and glassmorphism cards.
Visual elements: Only pets (cats, dogs, rabbits, birds) — absolutely NO humans, NO hands, NO people.
NO logos, NO brand names, NO watermarks, NO clinic names anywhere.
Background: Smooth gradient purple-to-magenta with soft bokeh light orbs.
Aesthetic: Minimalist luxury, ultra-clean lines, premium medical feel.
"""

STYLE_EDITORIAL = """
Cinematic editorial-grade pet photography composited into a social media design.
Lighting: Soft golden-hour side lighting with gentle purple ambient fill.
Subject: Only the pet (cat or dog) — shot at eye level, shallow depth of field, sharp focus on eyes.
Absolutely NO humans, NO hands, NO people, NO faces visible anywhere in the frame.
NO logos, NO brand names, NO watermarks, NO text overlays.
Color grading: Warm highlights, cool purple shadows, filmic grain.
Environment: Clean, minimal — soft neutral or purple-toned abstract background.
Quality: 8K detail, professional DSLR look (Sony A7R IV aesthetic).
"""

STYLE_STORY = """
Vertical 9:16 Instagram Story — premium pet content card.
Layout: Full-bleed purple-to-magenta gradient background.
Center: A single stunning pet portrait (cat or dog) inside a rounded glassmorphism card.
NO humans, NO hands, NO people anywhere.
NO logos, NO brand names, NO watermarks, NO clinic names.
Mood: Warm, inviting, soft ambient glow around the pet card.
Quality: Crisp, high-resolution, magazine-quality composition.
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
        return random.choice([STYLE_INFOGRAPHIC, STYLE_EDITORIAL])

    def _build_prompt(self, description: str, aspect: str, style_override: str | None = None) -> str:
        style = style_override or self._get_random_style()
        ratio_hint = "square 1:1 format" if aspect == "1:1" else "vertical 9:16 story format"
        return f"{description} | {style} | Format: {ratio_hint}."

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
            prompt += " " + STYLE_STORY.replace("\n", " ")
        return prompt, aspect_ratio

    def generate_tip_image(self, topic: str, content_format: str = "post") -> Path | None:
        """يولّد صورة نصيحة بيطرية — تعليمية، محايدة، بدون أشخاص"""
        try:
            base_prompt = (
                f"A stunning veterinary educational image about: '{topic}'. "
                "Feature a photogenic pet (cat or dog) as the sole subject in a clean, modern setting. "
                "The pet should be in a context that visually illustrates the health tip — e.g. near healthy food, "
                "grooming tools, a cozy bed, or veterinary instruments displayed neatly. "
                "Absolutely NO humans, NO hands, NO people visible. "
                "NO text, NO logos, NO brand names, NO watermarks. "
                "Color palette: deep purple and magenta tones in the environment. "
                "Photorealistic, magazine-quality, warm inviting lighting."
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
        """يولّد صورة ترند — مرتبطة بالموضوع الرائج، محايدة بالكامل"""
        try:
            base_prompt = (
                f"A creative, eye-catching pet image inspired by the trending topic: '{trend}'. "
                f"{'Mood hint: ' + caption_hint[:80] + '. ' if caption_hint else ''}"
                "Show a charismatic pet (cat or dog) in a fun, dynamic, or surprising pose/setting "
                "that cleverly relates to the trend concept. "
                "Absolutely NO humans, NO hands, NO people visible. "
                "NO text, NO logos, NO brand names, NO watermarks. "
                "Vibrant purple and magenta color accents. High-energy, scroll-stopping composition. "
                "Professional photography quality with dramatic lighting."
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
        """يولّد صورة يوميات — لقطة واقعية للحيوان، بدون بشر"""
        try:
            base_prompt = (
                f"A warm, candid-style photograph of a pet in a veterinary clinic environment: '{theme}'. "
                "Show the pet (cat or dog) on an examination table or in a clean clinic waiting area. "
                "Visible veterinary instruments, stethoscope, or medical supplies arranged around the pet. "
                "The scene feels authentic and behind-the-scenes — documentary style. "
                "Absolutely NO humans, NO hands, NO people, NO faces anywhere in the image. "
                "NO text, NO logos, NO brand names, NO watermarks. "
                "Soft purple and lavender ambient tones. Warm overhead lighting. "
                "High-resolution, natural candid feel, slightly desaturated for realism."
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
        """يولّد صورة عاطفية — تركيز على الحيوان فقط، بدون بشر"""
        try:
            base_prompt = (
                f"A deeply emotional, cinematic pet portrait: '{theme}'. "
                "A single pet (cat or dog) with soulful, expressive eyes looking directly at the camera. "
                "The emotion should be palpable — hope, love, resilience, or gentle vulnerability. "
                "Soft, dreamy lighting with golden highlights and deep purple shadow tones. "
                "Absolutely NO humans, NO hands, NO people, NO faces anywhere. "
                "NO text, NO logos, NO brand names, NO watermarks. "
                "Shallow depth of field, cinematic bokeh, fine art photography quality. "
                "The image alone should evoke deep emotion and stop someone from scrolling."
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
        """يولّد صورة خدمة بيطرية — عرض احترافي بدون أشخاص أو علامات"""
        try:
            base_prompt = (
                f"A premium veterinary service showcase image: '{service}'. "
                "Feature a healthy, well-groomed pet (cat or dog) alongside relevant medical equipment — "
                "stethoscope, syringes, lab vials, dental tools, or surgical instruments arranged artistically. "
                "Clean, modern medical aesthetic — sterile white surfaces with purple accent lighting. "
                "Absolutely NO humans, NO hands, NO people, NO faces. "
                "NO text, NO logos, NO brand names, NO watermarks, NO clinic names. "
                "Deep purple (#7B2FBE) and white color scheme. "
                "Trust-building, clinical yet warm imagery. Studio-quality product photography feel."
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
        """يولّد محتوى متنوع — كل نوع مستقل تماماً عن الأنواع الأخرى"""
        import random
        
        # كل نوع محتوى مستقل بذاته ولا يعتمد على أي نوع آخر
        choices = ["tip", "emotional", "daily_life", "service"]
        
        # أضف الترند فقط إذا كان متاحاً
        latest_trend = None
        try:
            from database import content_queue as cq
            trends = cq.list_trends_today(limit=1)
            if trends:
                latest_trend = trends[0].get("trend_topic")
                choices.append("trend")
        except Exception:
            pass
            
        choice = random.choice(choices)
        logger.info("Auto-generating content: type={}, format={}", choice, content_format)
        
        if choice == "tip":
            return self.generate_tip_image(random.choice(VET_TIP_TOPICS), content_format)
        elif choice == "emotional":
            return self.generate_emotional_image(random.choice(EMOTIONAL_THEMES), content_format)
        elif choice == "daily_life":
            return self.generate_daily_life_image(random.choice(DAILY_LIFE_THEMES), content_format)
        elif choice == "service":
            return self.generate_service_image(random.choice(SERVICE_TOPICS), content_format)
        elif choice == "trend" and latest_trend:
            return self.generate_trend_image(latest_trend, content_format=content_format)
        
        # Fallback
        return self.generate_tip_image(random.choice(VET_TIP_TOPICS), content_format)


nano_banana = NanaBananaService()

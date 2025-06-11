import os
import time
import base64
import logging
import requests
from io import BytesIO
from PIL import Image
from cloudinary.uploader import upload as cloudinary_upload

# Constants
SEGMIND_COOLDOWN_SECONDS = 3600
GETIMG_COOLDOWN_SECONDS = 1800

# Call counters
segmind_calls = segmind_failures = getimg_calls = getimg_failures = 0
last_segmind_rate_limit_time = last_getimg_rate_limit_time = None


def build_prompt(base_prompt, gender=None, current_weight=None, desired_weight=None, height_m=None):
    """
    Builds a final prompt string incorporating body, gender, and optional height cues.
    """
    # Weight difference to infer slimmer vs stronger
    try:
        diff = float(desired_weight or 0) - float(current_weight or 0)
    except Exception:
        logging.warning("⚠️ Invalid weight values; defaulting to neutral body prompt.")
        diff = 0

    if abs(diff) < 2:
        body_phrase = "similar body type"
    elif diff < 0:
        body_phrase = "slimmer, toned, healthy appearance"
    else:
        body_phrase = "stronger, athletic build"

    # Gender adjustments
    gender_phrase = "realistic human body appearance"
    if gender:
        g = gender.lower()
        if g.startswith(('m','male','man')):
            gender_phrase = "masculine features, realistic male fitness aesthetic"
        elif g.startswith(('f','female','woman')):
            gender_phrase = "feminine features, realistic female fitness aesthetic"

    # Height cue
    height_phrase = None
    if isinstance(height_m, (int, float)):
        height_phrase = f"height {height_m:.2f} m"

    # Assemble final prompt components
    parts = [
        base_prompt,
        body_phrase,
        gender_phrase,
    ]
    if height_phrase:
        parts.append(height_phrase)
    parts.extend(["photorealistic", "preserve face", "close resemblance to original photo"])

    final = ", ".join(parts)
    logging.info(f"📝 Final prompt: {final}")
    return final


def call_segmind(prompt, image_url):
    global segmind_calls, segmind_failures, last_segmind_rate_limit_time
    segmind_calls += 1

    # Cooldown guard
    if last_segmind_rate_limit_time and time.time() - last_segmind_rate_limit_time < SEGMIND_COOLDOWN_SECONDS:
        rem = SEGMIND_COOLDOWN_SECONDS - int(time.time() - last_segmind_rate_limit_time)
        logging.warning(f"⏳ Segmind cooldown active: {rem}s remaining.")
        return None

    api_key = os.getenv('SEGMIND_API_KEY')
    if not api_key:
        logging.error("🔐 Missing Segmind API key.")
        return None

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "face_image": image_url,
        "a_prompt": "best quality, extremely detailed",
        "n_prompt": "blurry, cartoon, unrealistic, bad anatomy",
        "num_samples": 1,
        "strength": 0.3,
        "guess_mode": False
    }
    resp = requests.post("https://api.segmind.com/v1/instantid", json=payload, headers=headers)
    status, ct, text = resp.status_code, resp.headers.get('Content-Type',''), (resp.text or '')[:200]

    if status == 200:
        # Raw image bytes path
        if ct.startswith('image/'):
            try:
                buf = BytesIO(resp.content)
                Image.open(buf).verify(); buf.seek(0)
            except Exception as e:
                segmind_failures += 1
                logging.error(f"❌ Bad Segmind image bytes: {e}")
                return None
            up = cloudinary_upload(file=buf, folder='webhook_images')
            return up.get('secure_url')

        # JSON response path
        if 'application/json' in ct:
            try:
                data = resp.json()
            except Exception as e:
                segmind_failures += 1
                logging.error(f"❌ Segmind JSON decode error: {e}; text={text}")
                return None
            out = data.get('output')
            return out[0] if isinstance(out, list) else out

        segmind_failures += 1
        logging.error(f"❌ Unexpected Segmind content-type {ct}: {text}")
        return None

    if status == 429:
        last_segmind_rate_limit_time = time.time()
        segmind_failures += 1
        logging.warning(f"🚫 Rate-limited by Segmind: {text}")
    elif status == 401:
        segmind_failures += 1
        logging.error(f"🔐 Segmind auth failed (401): {text}")
    else:
        segmind_failures += 1
        logging.error(f"❌ Segmind error {status}: {text}")

    return None


def call_getimg(prompt, image_url):
    global getimg_calls, getimg_failures, last_getimg_rate_limit_time
    getimg_calls += 1
    # ... unchanged fallback logic ...
    return None


def generate_goal_image(base_prompt, image_url, gender=None, current_weight=None, desired_weight=None, height_m=None):
    """
    Downloads, uploads, enhances face via Segmind, then full body via Getimg.
    Accepts height_m to pass into prompt.
    """
    # Download + verify original
    resp = requests.get(image_url, timeout=10)
    try:
        resp.raise_for_status()
        buf = BytesIO(resp.content)
        Image.open(buf).verify(); buf.seek(0)
    except Exception as e:
        logging.error(f"❌ Invalid original image: {e}")
        return None

    # Upload to Cloudinary for consistent sizing
    up = cloudinary_upload(file=buf, folder='webhook_images', transformation=[{'width':512,'height':512,'crop':'fit'}])
    uploaded_url = up.get('secure_url')
    logging.info(f"✅ Uploaded for generation: {uploaded_url}")

    # Build enhanced prompt (includes height)
    enhanced = build_prompt(base_prompt, gender, current_weight, desired_weight, height_m)

    # Face enhancement
    face_url = call_segmind(enhanced, uploaded_url) or uploaded_url

    # Full-body generation
    final_url = call_getimg(enhanced, face_url) or face_url
    return final_url

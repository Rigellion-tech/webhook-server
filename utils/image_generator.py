# utils/image_generator.py
import os
import time
import base64
import logging
import requests
from io import BytesIO
from PIL import Image
from cloudinary.uploader import upload as cloudinary_upload

SEGMIND_COOLDOWN_SECONDS = 3600  # 1 hour
GETIMG_COOLDOWN_SECONDS = 1800   # 30 minutes

# Track state
segmind_calls = segmind_failures = getimg_calls = getimg_failures = 0
last_segmind_rate_limit_time = last_getimg_rate_limit_time = None

def build_prompt(base_prompt, gender=None, current_weight=None, desired_weight=None):
    try:
        weight_diff = float(desired_weight or 0) - float(current_weight or 0)
    except Exception:
        logging.warning("⚠️ Invalid weight values provided. Defaulting to 0.")
        weight_diff = 0

    if abs(weight_diff) < 2:
        body_prompt = "similar body type"
    elif weight_diff < 0:
        body_prompt = "slimmer, toned, healthy appearance"
    else:
        body_prompt = "stronger, athletic build"

    gender_prompt = "realistic human body appearance"
    if gender:
        g = gender.lower()
        if g in ["male", "man"]:
            gender_prompt = "masculine features, realistic male fitness aesthetic"
        elif g in ["female", "woman"]:
            gender_prompt = "feminine features, realistic female fitness aesthetic"

    final_prompt = (
        f"{base_prompt}, {body_prompt}, {gender_prompt}, "
        "photorealistic, preserve face, close resemblance to original photo"
    )
    logging.info(f"📝 Final prompt: {final_prompt}")
    return final_prompt
def call_segmind(enhanced_prompt, uploaded_image_url):
    global segmind_calls, segmind_failures, last_segmind_rate_limit_time
    segmind_calls += 1

    try:
        api_key = os.environ.get('SEGMIND_API_KEY')
        if not api_key:
            logging.error("🔐 Segmind API key missing.")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": enhanced_prompt,
            "face_image": uploaded_image_url,
            "a_prompt": "best quality, extremely detailed",
            "n_prompt": "blurry, cartoon, unrealistic, distorted, bad anatomy",
            "num_samples": 1,
            "strength": 0.3,
            "guess_mode": False
        }

        response = requests.post("https://api.segmind.com/v1/instantid", headers=headers, json=payload)

        if response.status_code == 200:
            result = response.json()
            return result.get("output")[0] if isinstance(result.get("output"), list) else result.get("output")

        elif response.status_code == 429:
            last_segmind_rate_limit_time = time.time()
            segmind_failures += 1
            logging.warning("🚫 Segmind rate-limited (429). Cooling down.")
        elif response.status_code == 401:
            segmind_failures += 1
            logging.error("🔐 Segmind auth failed (401). Check your API key.")
        else:
            segmind_failures += 1
            logging.error(f"❌ Segmind API error {response.status_code}: {response.text}")

    except Exception:
        segmind_failures += 1
        logging.exception("❌ Segmind exception")

    return None
def call_getimg(enhanced_prompt, uploaded_image_url):
    global getimg_calls, getimg_failures, last_getimg_rate_limit_time
    getimg_calls += 1

    if last_getimg_rate_limit_time:
        seconds_since = time.time() - last_getimg_rate_limit_time
        if seconds_since < GETIMG_COOLDOWN_SECONDS:
            remaining = GETIMG_COOLDOWN_SECONDS - int(seconds_since)
            logging.warning(f"⏳ Getimg cooldown active. {remaining} seconds remaining.")
            return None

    try:
        img_response = requests.get(uploaded_image_url)
        img_response.raise_for_status()
        base64_img = base64.b64encode(img_response.content).decode('utf-8')

        headers = {
            "Authorization": f"Bearer {os.environ.get('GETIMG_API_KEY')}",
            "Content-Type": "application/json"
        }

        fallback_models = [
            "revAnimated_v122",
            "dreamshaper_v8",
            "realisticVision_v40"
        ]

        for model_name in fallback_models:
            payload = {
                "prompt": enhanced_prompt,
                "image": base64_img,
                "model": model_name,
                "controlnet_model": "control_v11p_sd15_openpose",
                "controlnet_type": "pose",
                "strength": 0.4,
                "negative_prompt": "cartoon, blurry, ugly, distorted face, low quality",
                "guidance": 7,
                "num_images": 1
            }

            logging.info(f"🧪 Trying Getimg model: {model_name}")

            response = requests.post(
                "https://api.getimg.ai/v1/stable-diffusion/image-to-image",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                logging.info(f"✅ Image generated via Getimg model: {model_name}")
                return result["data"][0]["url"]

            elif response.status_code == 429:
                last_getimg_rate_limit_time = time.time()
                getimg_failures += 1
                logging.warning(f"🚫 Getimg rate-limited (429). Cooling down.")
                return None

            else:
                logging.warning(f"⚠️ Getimg model '{model_name}' failed: {response.status_code} ➝ {response.text}")

        getimg_failures += 1
        logging.error("❌ All Getimg model attempts failed.")

    except Exception:
        getimg_failures += 1
        logging.exception("❌ Getimg exception occurred")

    return None



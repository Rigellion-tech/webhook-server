# utils/image_generator.py
import os
import time
import base64
import logging
import requests
from io import BytesIO
from PIL import Image
from cloudinary.uploader import upload as cloudinary_upload

SEGMIND_COOLDOWN_SECONDS = 3600
GETIMG_COOLDOWN_SECONDS = 1800

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
        f"{base_prompt}, {body_prompt}, {gender_prompt}, photorealistic, preserve face, close resemblance to original photo"
    )
    logging.info(f"📝 Final prompt: {final_prompt}")
    return final_prompt


def call_segmind(prompt, image_url):
    global segmind_calls, segmind_failures, last_segmind_rate_limit_time
    segmind_calls += 1

    # --- cooldown guard ---
    if last_segmind_rate_limit_time:
        elapsed = time.time() - last_segmind_rate_limit_time
        if elapsed < SEGMIND_COOLDOWN_SECONDS:
            rem = SEGMIND_COOLDOWN_SECONDS - int(elapsed)
            logging.warning(f"⏳ Segmind cooldown active. {rem}s remaining.")
            return None

    try:
        api_key = os.getenv('SEGMIND_API_KEY')
        if not api_key:
            logging.error("🔐 Segmind API key missing.")
            return None

        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "face_image": image_url,
            "a_prompt": "best quality, extremely detailed",
            "n_prompt": "blurry, cartoon, unrealistic, distorted, bad anatomy",
            "num_samples": 1,
            "strength": 0.3,
            "guess_mode": False
        }

        response = requests.post("https://api.segmind.com/v1/instantid",
                                 headers=headers, json=payload)
        status = response.status_code
        text_snip = (response.text or "")[:200]

        # 200 OK → safe‐guard JSON decode
        if status == 200:
            ct = response.headers.get("Content-Type", "")
            if "application/json" not in ct:
                segmind_failures += 1
                logging.error(f"❌ Segmind returned non-JSON ({ct}): {text_snip}")
                return None
            try:
                result = response.json()
            except ValueError as e:
                segmind_failures += 1
                logging.error(f"❌ Segmind JSON decode failed: {e}; text: {text_snip}")
                return None

            output = result.get("output")
            return output[0] if isinstance(output, list) else output

        # handle rate‐limit
        elif status == 429:
            last_segmind_rate_limit_time = time.time()
            segmind_failures += 1
            logging.warning(f"🚫 Segmind rate-limited: {status} → {text_snip}")

        # auth error
        elif status == 401:
            segmind_failures += 1
            logging.error(f"🔐 Segmind auth failed: {status} → {text_snip}")

        # any other error
        else:
            segmind_failures += 1
            logging.error(f"❌ Segmind API error {status}: {text_snip}")

    except Exception:
        segmind_failures += 1
        logging.exception("❌ Segmind exception")

    return None


def call_getimg(prompt, image_url):
    global getimg_calls, getimg_failures, last_getimg_rate_limit_time
    getimg_calls += 1

    if last_getimg_rate_limit_time:
        seconds_since = time.time() - last_getimg_rate_limit_time
        if seconds_since < GETIMG_COOLDOWN_SECONDS:
            remaining = GETIMG_COOLDOWN_SECONDS - int(seconds_since)
            logging.warning(f"⏳ Getimg cooldown active. {remaining}s remaining.")
            return None

    try:
        # download + base64-encode
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        base64_img = base64.b64encode(img_response.content).decode('utf-8')

        headers = {
            "Authorization": f"Bearer {os.getenv('GETIMG_API_KEY')}",
            "Content-Type": "application/json"
        }

        # TODO: replace these with the exact model IDs your plan supports
        fallback_models = [
            "realistic-vision-v5",
            "juggernaut-xl-v8",
            "dreamshaper-v7"
        ]

        for model_name in fallback_models:
            payload = {
                "prompt": prompt,
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
            status = response.status_code
            text_snip = (response.text or "")[:200]

            if status == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    getimg_failures += 1
                    logging.error(f"❌ Getimg JSON decode failed: {e}; text: {text_snip}")
                    continue

                logging.info(f"✅ Image generated via Getimg model: {model_name}")
                return data["data"][0]["url"]

            elif status == 429:
                last_getimg_rate_limit_time = time.time()
                getimg_failures += 1
                logging.warning(f"🚫 Getimg rate-limited: {status} → {text_snip}")
                return None

            else:
                logging.warning(f"⚠️ Getimg model '{model_name}' failed: {status} → {text_snip}")

        getimg_failures += 1
        logging.error("❌ All Getimg model attempts failed.")

    except Exception:
        getimg_failures += 1
        logging.exception("❌ Getimg exception occurred")

    return None


def generate_goal_image(prompt, image_url, gender=None, current_weight=None, desired_weight=None):
    try:
        logging.info(f"🌐 Downloading image from: {image_url}")
        img_response = requests.get(image_url, stream=True, timeout=10)
        img_response.raise_for_status()

        image_bytes = BytesIO(img_response.content)
        try:
            Image.open(image_bytes).verify()
            image_bytes.seek(0)
        except Exception:
            logging.error("❌ Downloaded file is not a valid image.")
            return None

        upload_result = cloudinary_upload(
            file=image_bytes,
            folder="webhook_images",
            transformation=[{"width": 512, "height": 512, "crop": "fit"}]
        )
        uploaded_image_url = upload_result.get("secure_url")
        logging.info(f"✅ Image uploaded to Cloudinary: {uploaded_image_url}")

        enhanced_prompt = build_prompt(prompt, gender, current_weight, desired_weight)

        # 1️⃣ Face‐enhancement via Segmind (with cooldown + safe JSON parsing)
        face_enhanced_url = call_segmind(enhanced_prompt, uploaded_image_url)
        if not face_enhanced_url:
            logging.warning("⚠️ Segmind failed. Falling back to original upload.")
            face_enhanced_url = uploaded_image_url

        # 2️⃣ Full‐body via Getimg (then final fallback to face_enhanced_url)
        final_result_url = call_getimg(enhanced_prompt, face_enhanced_url)
        if not final_result_url:
            logging.warning("⚠️ Getimg failed. Falling back to face‐enhanced image.")
            final_result_url = face_enhanced_url

        return final_result_url

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to download image from URL: {image_url} ➝ {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Cloudinary upload failed ➝ {e}")
        return None

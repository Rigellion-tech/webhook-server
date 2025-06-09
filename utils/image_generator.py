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

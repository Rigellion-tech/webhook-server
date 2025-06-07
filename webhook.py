from flask import Flask, request, jsonify
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import requests
from cloudinary.uploader import upload as cloudinary_upload
from cloudinary.utils import cloudinary_url
import cloudinary
import time
import base64
from io import BytesIO
from PIL import Image
from fitness_utils import (
    calculate_age,
    pounds_to_kg,
    get_field_value,
    generate_workout_plan,
    create_pdf_with_workout
)


# Configure environment-based secrets
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY")
GETIMG_API_KEY = os.getenv("GETIMG_API_KEY")

# Keep track of when we got rate limited
last_segmind_rate_limit_time = None
SEGMIND_COOLDOWN_SECONDS = 3600  # 1 hour cooldown

last_getimg_rate_limit_time = None
GETIMG_COOLDOWN_SECONDS = 1800  # 30 minutes


# Cloudinary configuration
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API usage counters
segmind_calls = 0
segmind_failures = 0
getimg_calls = 0
getimg_failures = 0

app = Flask(__name__)

@app.before_request
def log_request():
    logging.info(f"🔍 Incoming request: {request.method} {request.path}")

# ----------------------------
# Helper functions
# ----------------------------
def calculate_age(birthdate_str):
    try:
        dob = datetime.strptime(birthdate_str, "%Y-%m-%d")
        today = datetime.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception as e:
        logging.warning(f"Failed to parse birthdate: {e}")
        return None

def pounds_to_kg(lbs):
    try:
        return round(float(lbs) * 0.453592, 2)
    except:
        return None

def get_field_value(fields, *label_keywords):
    for keyword in label_keywords:
        for field in fields:
            label = field.get('label', '').lower()
            value = field.get('value')
            if keyword.lower() in label:
                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        return value[0].get('url')
                    elif value and isinstance(value[0], str):
                        return value[0]
                return value
    return None

# ----------------------------
# Email sending function
# ----------------------------
def send_email(to_email, subject, body_html):
    from_email = "daydreamforgephyton.ai@gmail.com"

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    plain_text = "Your email client does not support HTML emails. Please view this message in a modern client."

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, EMAIL_APP_PASSWORD)
            server.send_message(msg)
            logging.info("✅ Email sent successfully.")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")

# ----------------------------
# AI Image Generation
# ----------------------------
def generate_goal_image(prompt, image_url, gender=None, current_weight=None, desired_weight=None):
    global segmind_calls, segmind_failures, last_segmind_rate_limit_time
    segmind_calls = segmind_calls if 'segmind_calls' in globals() else 0
    segmind_failures = segmind_failures if 'segmind_failures' in globals() else 0
    last_segmind_rate_limit_time = last_segmind_rate_limit_time if 'last_segmind_rate_limit_time' in globals() else None

    def build_prompt():
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

        logging.info(f"🧠 Weight diff: {weight_diff} ➝ Body prompt: '{body_prompt}'")
        logging.info(f"🧬 Gender input: '{gender}' ➝ Gender prompt: '{gender_prompt}'")

        final_prompt = (
            f"{prompt}, {body_prompt}, {gender_prompt}, "
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
                "realistic-vision-v5",
                "dreamshaper-v8",
                "sdxl-lightning",
                "rev-animated-v1"
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


    # 🧠 Start image download & upload flow
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

        enhanced_prompt = build_prompt()

        result = call_segmind(enhanced_prompt, uploaded_image_url)
        if result:
            logging.info("🎯 Image generated via Segmind.")
            return result

        logging.info("🔁 Falling back to Getimg...")
        result = call_getimg(enhanced_prompt, uploaded_image_url)
        if result:
            logging.info("🎯 Image generated via Getimg.")
        return result

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to download image from URL: {image_url} ➝ {e}")
        return None
    except Exception as e:
        logging.error(f"❌ Cloudinary upload failed ➝ {e}")
        return None
# ----------------------------
# Webhook route
# ----------------------------
# ----------------------------
# Webhook route
# ----------------------------
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.get_json(force=True)
        logging.info("Raw received data: %s", data)
    except Exception as e:
        logging.error("Failed to parse JSON: %s", str(e))
        return jsonify({'error': 'Invalid JSON'}), 400

    if not data or 'data' not in data or 'fields' not in data['data']:
        logging.warning("Invalid or missing 'fields'")
        return jsonify({'error': 'Invalid request payload'}), 400

    fields = data['data']['fields']

    first_name = get_field_value(fields, 'first name', 'name')
    email = get_field_value(fields, 'email')
    gender = get_field_value(fields, 'gender', 'sex')
    date_of_birth = get_field_value(fields, 'date of birth', 'dob')
    photo_url = get_field_value(fields, 'photo', 'image')
    current_weight_lbs = get_field_value(fields, "current weight", "current body weight", "weight now")
    desired_weight_lbs = get_field_value(fields, "desired weight", "target weight", "goal weight")

    age = calculate_age(date_of_birth)
    current_weight_kg = pounds_to_kg(current_weight_lbs)
    desired_weight_kg = pounds_to_kg(desired_weight_lbs)

    ai_prompt = f"{age}-year-old {gender} person at {desired_weight_lbs} lbs, athletic, healthy body, fit appearance, soft lighting, full body studio portrait"
    image_url = generate_goal_image(ai_prompt, photo_url, gender=gender, current_weight=current_weight_lbs, desired_weight=desired_weight_lbs)

    workout_plan_html = generate_workout_plan(age, gender, current_weight_kg, desired_weight_kg)
    pdf_url = create_pdf_with_workout(image_url, workout_plan_html)

    logging.info(f"Generated Image URL: {image_url}")
    logging.info(f"📊 Segmind calls: {segmind_calls}, Failures: {segmind_failures}")

    if email:
        email_body = f"""
Hi {first_name},<br><br>

Thanks for submitting your fitness form! Here's a quick summary:<br>
<ul>
  <li><b>Age:</b> {age}</li>
  <li><b>Gender:</b> {gender}</li>
  <li><b>Current Weight:</b> {current_weight_lbs} lbs ({current_weight_kg} kg)</li>
  <li><b>Desired Weight:</b> {desired_weight_lbs} lbs ({desired_weight_kg} kg)</li>
</ul>

<h3>💡 AI-Generated Fitness Goal Preview:</h3>
<img src="{image_url}" alt="AI fitness goal" style="max-width: 100%; height: auto;" /><br><br>

<h3>🏋️ Personalized Workout Plan:</h3>
{workout_plan_html}<br><br>

📄 <b>Download Your Full Plan as PDF:</b> <a href="{pdf_url}" target="_blank">Click Here</a><br><br>

Stay strong,<br>
The DayDream Forge Team
"""
        send_email(to_email=email, subject="Your AI Fitness Image & Summary", body_html=email_body)

    return jsonify({'status': 'received'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


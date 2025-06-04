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

# Configure environment-based secrets
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY")
GETIMG_API_KEY = os.getenv("GETIMG_API_KEY")

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

def get_field_value(fields, label_keyword):
    for field in fields:
        label = field.get('label', '').lower()
        value = field.get('value')
        if label_keyword.lower() in label:
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value[0].get('url')
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
    global segmind_calls, segmind_failures
    try:
        upload_result = cloudinary_upload(
            image_url,
            folder="webhook_images",
            transformation=[{"width": 512, "height": 512, "crop": "fit"}]
        )
        uploaded_image_url = upload_result.get("secure_url")
        logging.info(f"✅ Image uploaded to Cloudinary: {uploaded_image_url}")

        weight_diff = float(desired_weight or 0) - float(current_weight or 0)
        if abs(weight_diff) < 2:
            body_prompt = "similar body type"
        elif weight_diff < 0:
            body_prompt = "slimmer, toned, healthy appearance"
        else:
            body_prompt = "stronger, athletic build"

        gender_prompt = ""
        if gender:
            if gender.lower() in ["male", "man"]:
                gender_prompt = "masculine features, realistic male fitness aesthetic"
            elif gender.lower() in ["female", "woman"]:
                gender_prompt = "feminine features, realistic female fitness aesthetic"
            else:
                gender_prompt = "realistic human body appearance"

        enhanced_prompt = f"{prompt}, {body_prompt}, {gender_prompt}, photorealistic, preserve face, close resemblance to original photo"

        segmind_calls += 1
        headers = {
            "Authorization": f"Bearer {SEGMIND_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": enhanced_prompt,
            "image_url": uploaded_image_url,
            "a_prompt": "best quality, extremely detailed",
            "n_prompt": "blurry, cartoon, unrealistic, distorted, bad anatomy",
            "num_samples": 1,
            "strength": 0.3,
            "guess_mode": False
        }
        response = requests.post("https://api.segmind.com/v1/instantid", headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            image_out = result.get("output")
            if isinstance(image_out, list):
                return image_out[0]
            return image_out
        else:
            segmind_failures += 1
            logging.error(f"❌ Segmind API error ({response.status_code}): {response.text}")
            return None

    except Exception as e:
        segmind_failures += 1
        logging.exception("❌ Unexpected error during image generation")
        return None

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

    first_name = get_field_value(fields, 'first name')
    email = get_field_value(fields, 'email')
    gender = get_field_value(fields, 'gender')
    date_of_birth = get_field_value(fields, 'date of birth')
    photo_url = get_field_value(fields, 'photo')
    current_weight_lbs = get_field_value(fields, "current body weight")
    desired_weight_lbs = get_field_value(fields, "desired weight")

    age = calculate_age(date_of_birth)
    current_weight_kg = pounds_to_kg(current_weight_lbs)
    desired_weight_kg = pounds_to_kg(desired_weight_lbs)

    ai_prompt = f"{age}-year-old {gender} person at {desired_weight_lbs} lbs, athletic, healthy body, fit appearance, soft lighting, full body studio portrait"
    image_url = generate_goal_image(ai_prompt, photo_url, gender=gender, current_weight=current_weight_lbs, desired_weight=desired_weight_lbs)

    logging.info(f"Generated Image URL: {image_url}")
    logging.info(f"📊 Segmind calls: {segmind_calls}, Failures: {segmind_failures}")

    if email:
        email_body = f"""
Hi {first_name},

Thanks for submitting your fitness form!

Here's a quick summary:
- Age: {age}
- Gender: {gender}
- Current Weight: {current_weight_lbs} lbs ({current_weight_kg} kg)
- Desired Weight: {desired_weight_lbs} lbs ({desired_weight_kg} kg)

💡 Here's a preview of your future fitness goal:
<img src=\"{image_url}\" alt=\"AI generated fitness goal\" style=\"max-width: 100%; height: auto;\" />

Stay tuned for your workout plan!

Cheers,  
The DayDream Forge Team
"""
        send_email(to_email=email, subject="Your AI Fitness Image & Summary", body_html=email_body)

    return jsonify({'status': 'received'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

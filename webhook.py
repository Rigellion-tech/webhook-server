from flask import Flask, request, jsonify
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import replicate
import os
import requests
from cloudinary.uploader import upload as cloudinary_upload
from cloudinary.utils import cloudinary_url
import cloudinary

# Configure environment-based secrets
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate.api_token = REPLICATE_API_TOKEN

EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

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
def generate_goal_image(prompt, image_url):
    if not REPLICATE_API_TOKEN:
        logging.error("❌ Missing Replicate API token. Cannot generate image.")
        return None

    try:
        replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

        upload_result = cloudinary_upload(
            image_url,
            folder="webhook_images",
            transformation=[{"width": 512, "height": 512, "crop": "limit"}]
        )
        uploaded_image_url = upload_result.get("secure_url")
        logging.info(f"✅ Image uploaded to Cloudinary: {uploaded_image_url}")

        output = replicate_client.run(
            "stability-ai/stable-diffusion-img2img:15a3689ee13b0d2616e98820eca31d4c3abcd36672df6afce5cb6feb1d66087d",
            input={
                "image": uploaded_image_url,
                "prompt": prompt,
                "strength": 0.5,
                "num_outputs": 1,
                "guidance_scale": 7.5,
                "num_inference_steps": 30
            }
        )

        if output:
            logging.info("✅ Image generation successful")
            return output[0] if isinstance(output, list) else output
        else:
            logging.error("❌ No output from Replicate")
            return None

    except replicate.exceptions.ReplicateError as e:
        if "You need to set up billing" in str(e):
            logging.error("❌ Billing not yet active. Wait and retry later.")
        else:
            logging.exception("❌ Replicate error during image generation")
        return None

    except Exception as e:
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
    image_url = generate_goal_image(ai_prompt, photo_url)

    logging.info(f"Generated Image URL: {image_url}")

    if email:
        email_body = f"""
Hi {first_name},

Thanks for submitting your fitness form!

Here's a quick summary:
- Age: {age}
- Current Weight: {current_weight_lbs} lbs ({current_weight_kg} kg)
- Desired Weight: {desired_weight_lbs} lbs ({desired_weight_kg} kg)

💡 Here's a preview of your future fitness goal:
{image_url}

Stay tuned for your workout plan!

Cheers,  
The DayDream Forge Team
"""
        send_email(to_email=email, subject="Your AI Fitness Image & Summary", body_html=email_body)

    return jsonify({'status': 'received'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

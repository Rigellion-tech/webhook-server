from flask import Flask, request, jsonify
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import replicate
import os

# Load Replicate API token securely from environment
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if REPLICATE_API_TOKEN:
    client = replicate.Client(api_token=REPLICATE_API_TOKEN)
else:
    client = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

# -----------------------
# Email sending function
# -----------------------
def send_email(to_email, subject, body):
    from_email = "daydreamforgephyton.ai@gmail.com"
    app_password = os.getenv("EMAIL_APP_PASSWORD")  # Securely load email password from environment

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, app_password)
            server.send_message(msg)
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# ----------------------------
# AI Image Generation Function
# ----------------------------
def generate_goal_image(prompt):
    if not client:
        logging.error("Replicate client not initialized due to missing API token.")
        return None
    try:
        output_url = client.run(
            "lucataco/realistic-vision-v5.1",
            input={
                "prompt": prompt,
                "width": 512,
                "height": 768,
                "num_outputs": 1
            }
        )
        return output_url[0] if output_url else None
    except Exception as e:
        logging.error(f"❌ Image generation failed: {e}")
        return None

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

    logging.info("=== All Form Fields ===")
    for field in fields:
        logging.info(f"Label: {field.get('label')} | Type: {field.get('type')} | Value: {field.get('value')}")

    def get_field_value(label_keyword):
        for field in fields:
            label = field.get('label', '').lower()
            value = field.get('value')
            if label_keyword.lower() in label:
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return value[0].get('url')
                return value
        return None

    # Extract fields
    first_name = get_field_value('first name')
    last_name = get_field_value('last name')
    phone_number = get_field_value('phone number')
    date_of_birth = get_field_value('date of birth')
    email = get_field_value('email')
    home_address = get_field_value('home address')
    city_state_zip = get_field_value('city | state | zip')
    gender = get_field_value('gender')
    photo_url = get_field_value('photo')
    special_conditions = get_field_value('special health conditions')
    current_weight_lbs = get_field_value("current body weight")
    desired_weight_lbs = get_field_value("desired weight")

    # Calculated fields
    age = calculate_age(date_of_birth)
    current_weight_kg = pounds_to_kg(current_weight_lbs)
    desired_weight_kg = pounds_to_kg(desired_weight_lbs)

    # Generate image
    ai_prompt = f"{age}-year-old {gender} person at {desired_weight_lbs} lbs, athletic, healthy body, fit appearance, soft lighting, full body studio portrait"
    image_url = generate_goal_image(ai_prompt)

    # Logging
    logging.info("=== New Submission ===")
    logging.info(f"First Name: {first_name}")
    logging.info(f"Email: {email}")
    logging.info(f"Age: {age}")
    logging.info(f"Desired Weight: {desired_weight_lbs} lbs")
    logging.info(f"Generated Image URL: {image_url}")
    logging.info("======================")

    # Send email
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
        send_email(
            to_email=email,
            subject="Your AI Fitness Image & Summary",
            body=email_body
        )

    return jsonify({'status': 'received'}), 200

# ----------------------------
# App runner
# ----------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)



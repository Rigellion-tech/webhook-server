from flask import Flask, request, jsonify
import logging
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
    from_email = "daydreamforgephyton.ai@gmail.com"  # Replace this with your sender email
    app_password = "sbng biye byiw pdli"     # Replace with 16-character app password

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

# Helper to calculate age
def calculate_age(birthdate_str):
    try:
        dob = datetime.strptime(birthdate_str, "%Y-%m-%d")
        today = datetime.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception as e:
        logging.warning(f"Failed to parse birthdate: {e}")
        return None

# Helper to convert lbs to kg
def pounds_to_kg(lbs):
    try:
        return round(float(lbs) * 0.453592, 2)
    except:
        return None

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

    # Log all fields
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

    logging.info("=== New Submission ===")
    logging.info(f"First Name: {first_name}")
    logging.info(f"Last Name: {last_name}")
    logging.info(f"Phone Number: {phone_number}")
    logging.info(f"Date of Birth: {date_of_birth}")
    logging.info(f"Age: {age}")
    logging.info(f"Email: {email}")
    logging.info(f"Home Address: {home_address}")
    logging.info(f"City | State | Zip: {city_state_zip}")
    logging.info(f"Gender: {gender}")
    logging.info(f"Photo URL: {photo_url}")
    logging.info(f"Special Health Conditions: {special_conditions}")
    logging.info(f"Current Weight (lbs): {current_weight_lbs} | (kg): {current_weight_kg}")
    logging.info(f"Desired Weight (lbs): {desired_weight_lbs} | (kg): {desired_weight_kg}")
    logging.info("======================")

    # ------------------------
    # Send confirmation email
    # ------------------------
    if email:
        email_body = f"""
        Hi {first_name},

        Thanks for submitting your fitness form!

        Here's a quick summary of what you provided:
        - Age: {age}
        - Current Weight: {current_weight_lbs} lbs ({current_weight_kg} kg)
        - Desired Weight: {desired_weight_lbs} lbs ({desired_weight_kg} kg)

        You'll receive your AI-generated fitness image and plan shortly.

        Cheers,
        The Fitness AI Team
        """
        send_email(
            to_email=email,
            subject="Your Fitness Form Submission",
            body=email_body
        )

    return jsonify({'status': 'received'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
x

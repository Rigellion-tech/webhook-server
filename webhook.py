from flask import Flask, request, jsonify
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

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
    current_weight_lbs = get_field_value("current weight")
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

    return jsonify({'status': 'received'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


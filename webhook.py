# app.py
import logging
from flask import Flask, request, jsonify
from fitness_utils import (
    calculate_age,
    pounds_to_kg,
    get_field_value,
    generate_workout_plan,
    create_pdf_with_workout,
    create_pdf_plan_only
)
from utils.image_generator import generate_goal_image
from utils.email_utils import send_email

app = Flask(__name__)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@app.before_request
def log_request():
    logging.info(f"🔍 Incoming request: {request.method} {request.path}")

# ----------------------------
# Webhook: Image + Workout Plan
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

    # Extract form fields
    first_name = get_field_value(fields, 'first name', 'name')
    email = get_field_value(fields, 'email')
    gender = get_field_value(fields, 'gender', 'sex')
    date_of_birth = get_field_value(fields, 'date of birth', 'dob')
    photo_url = get_field_value(fields, 'photo', 'image')
    current_weight_lbs = get_field_value(fields, "current weight", "current body weight", "weight now")
    desired_weight_lbs = get_field_value(fields, "desired weight", "target weight", "goal weight")

    # Data transformations
    age = calculate_age(date_of_birth)
    current_weight_kg = pounds_to_kg(current_weight_lbs)
    desired_weight_kg = pounds_to_kg(desired_weight_lbs)

    # AI image generation
    ai_prompt = (
        f"{age}-year-old {gender} person at {desired_weight_lbs} lbs, "
        "athletic, healthy body, fit appearance, soft lighting, full-body studio portrait"
    )
    image_url = generate_goal_image(
        ai_prompt,
        photo_url,
        gender=gender,
        current_weight=current_weight_lbs,
        desired_weight=desired_weight_lbs
    )

    # Workout plan generation
    workout_plan_html = generate_workout_plan(
        age=age,
        gender=gender,
        current_weight_kg=current_weight_kg,
        desired_weight_kg=desired_weight_kg
    )

    # PDF creation
    pdf_url = None
    if image_url:
        pdf_url = create_pdf_with_workout(image_url, workout_plan_html)
    else:
        logging.warning("Skipping PDF creation because image generation failed.")

    # Send email response if email provided
    if email:
        pdf_section = (
            f'<b>Download Your Full Plan as PDF:</b> '
            f'<a href="{pdf_url}" target="_blank">Click Here</a><br><br>'
            if pdf_url else
            "<i>⚠️ PDF could not be generated due to image issue.</i><br><br>"
        )
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

{pdf_section}

Stay strong,<br>
The DayDream Forge Team
"""
        send_email(to_email=email, subject="Your AI Fitness Image & Summary", body_html=email_body)

    return jsonify({'status': 'received'}), 200

# ----------------------------
# Pure Data: Workout Plan Endpoint with Downloadable PDF
# ----------------------------
@app.route('/workout', methods=['POST'])
def handle_workout():
    data = request.get_json(force=True)
    required = ['age', 'gender', 'current_weight_kg', 'desired_weight_kg']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing one of: ' + ", ".join(required)}), 400

    plan_html = generate_workout_plan(
        age=data['age'],
        gender=data['gender'],
        current_weight_kg=data['current_weight_kg'],
        desired_weight_kg=data['desired_weight_kg'],
        activity_level=data.get('activity_level'),
        goal_timeline=data.get('goal_timeline'),
        preferences=data.get('preferences'),
        injuries=data.get('injuries'),
        sleep_quality=data.get('sleep_quality'),
        tracking_calories=data.get('tracking_calories'),
        notes=data.get('notes')
    )
    # Generate plan-only PDF
    plan_pdf_url = create_pdf_plan_only(plan_html)
    return jsonify({'plan_html': plan_html, 'pdf_url': plan_pdf_url}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

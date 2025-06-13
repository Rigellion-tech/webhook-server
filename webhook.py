import logging
import json
import time
from threading import Thread
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

# In-memory dedupe store
processed_ids = set()

# ----------------------------
# Utility: parse height strings into meters
# ----------------------------
def parse_height(raw):
    if not raw:
        return None
    r = raw.strip().lower()
    try:
        if r.endswith('cm'):
            return float(r[:-2].strip()) / 100
        if r.endswith('m'):
            return float(r[:-1].strip())
        if "'" in r:
            parts = r.split("'")
            feet = float(parts[0])
            inches = 0
            if len(parts) > 1:
                inches = float(parts[1].replace('"','').replace('in','').strip())
            return (feet * 12 + inches) * 0.0254
        val = float(r)
        if val > 3:
            return val / 100
        return val
    except Exception:
        logging.warning(f"⚠️ Invalid height format: '{raw}'")
        return None

# ----------------------------
# Background worker
# ----------------------------
def process_submission(data):
    try:
        fields = data['data']['fields']
        # Extract form fields
        first_name          = get_field_value(fields, 'first name', 'name')
        email               = get_field_value(fields, 'email')
        gender              = get_field_value(fields, 'gender', 'sex')
        date_of_birth       = get_field_value(fields, 'date of birth', 'dob')
        photo_url           = get_field_value(fields, 'photo', 'image')
        current_weight_lbs  = get_field_value(fields, 'current weight', 'current body weight', 'weight now')
        desired_weight_lbs  = get_field_value(fields, 'desired weight', 'target weight', 'goal weight')
        height_raw          = get_field_value(fields, 'height', 'height (cm)', 'height (ft)', 'height')

        # Parse height
        height_m = parse_height(height_raw)
        logging.info(f"Parsed height: {height_m}")

        # Data transformations
        age               = calculate_age(date_of_birth)
        current_weight_kg = pounds_to_kg(current_weight_lbs)
        desired_weight_kg = pounds_to_kg(desired_weight_lbs)

        # Build AI prompt
        ai_prompt = f"{age}-year-old {gender} at {desired_weight_lbs} lbs"
        if height_m:
            ai_prompt += f", {height_m:.2f} m tall"
        ai_prompt += ", athletic, healthy body, fit appearance, soft lighting, full-body studio portrait"

        # Generate image
        image_url = generate_goal_image(
            ai_prompt,
            photo_url,
            gender=gender,
            current_weight=current_weight_lbs,
            desired_weight=desired_weight_lbs,
            height_m=height_m
        )

        # Generate workout plan
        workout_plan_html = generate_workout_plan(
            age=age,
            gender=gender,
            current_weight_kg=current_weight_kg,
            desired_weight_kg=desired_weight_kg,
            height_m=height_m
        )

        # Create PDFs
        full_pdf_url = create_pdf_with_workout(image_url, workout_plan_html) if image_url else None
        plan_only_pdf_url = create_pdf_plan_only(workout_plan_html)

        # Send email
        if email:
            full_section = (f'<b>Full Plan (with image):</b> <a href="{full_pdf_url}">Download</a><br><br>' if full_pdf_url else '<i>⚠️ Full plan failed.</i><br><br>')
            plan_section = (f'<b>Plan Only:</b> <a href="{plan_only_pdf_url}">Download</a><br><br>' if plan_only_pdf_url else '<i>⚠️ Plan-only failed.</i><br><br>')
            email_body = f"""
Hi {first_name},<br><br>
Your fitness overview is ready!<br>
{full_section}{plan_section}
Stay strong!<br>
"""
            send_email(to_email=email, subject="Your AI Fitness Plan", body_html=email_body)

    except Exception as e:
        logging.exception(f"Error processing submission: {e}")

# ----------------------------
# Webhook endpoint
# ----------------------------
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logging.error(f"Invalid JSON: {e}")
        return jsonify({'error':'Invalid JSON'}), 400

    # Basic validation
    if not data or 'data' not in data or 'fields' not in data['data']:
        return jsonify({'error':'Bad payload'}), 400

    # Dedupe
    sub_id = data['data'].get('id') or str(hash(json.dumps(data)))
    if sub_id in processed_ids:
        return jsonify({'status':'duplicate'}), 200
    processed_ids.add(sub_id)

    # Ack and queue
    Thread(target=process_submission, args=(data,), daemon=True).start()
    return jsonify({'status':'queued'}), 200

# ----------------------------
# Pure data endpoint
# ----------------------------
@app.route('/workout', methods=['POST'])
def handle_workout():
    data = request.get_json(force=True)
    required = ['age','gender','current_weight_kg','desired_weight_kg']
    if not all(k in data for k in required):
        return jsonify({'error':'Missing fields'}), 400

    plan_html = generate_workout_plan(
        age=data['age'],
        gender=data['gender'],
        current_weight_kg=data['current_weight_kg'],
        desired_weight_kg=data['desired_weight_kg'],
        height_m=data.get('height_m')
    )
    plan_pdf_url = create_pdf_plan_only(plan_html)
    return jsonify({'plan_html':plan_html,'pdf_url':plan_pdf_url}),200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

import logging
import time
from datetime import datetime
from io import BytesIO
import requests
from fpdf import FPDF
from cloudinary.uploader import upload as cloudinary_upload
import os
import openai

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----------------------------
# Basic Utilities
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
                logging.info(f"🧩 Matching field '{label}' ➝ Raw value: {value}")

                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        return (value[0].get('url') or
                                value[0].get('text') or
                                value[0].get('label') or
                                str(value[0]))
                    elif value and isinstance(value[0], str):
                        return value[0]

                elif isinstance(value, dict):
                    return (value.get('text') or
                            value.get('label') or
                            value.get('value') or
                            str(value))

                elif isinstance(value, str):
                    return value

                # Fallback
                return str(value)
    return None

# ----------------------------
# GPT-Powered Workout Plan
# ----------------------------
def generate_workout_plan(
    age,
    gender,
    current_weight_kg,
    desired_weight_kg,
    activity_level=None,
    goal_timeline=None,
    preferences=None,
    injuries=None,
    sleep_quality=None,
    tracking_calories=None,
    notes=None
):
    """
    Generate a personalized, HTML-formatted workout and meal plan using GPT.
    """
    system_msg = {
        "role": "system",
        "content": (
            "You are a certified fitness coach. Create safe, efficient, and tailored workout plans. "
            "Always consider health conditions, timeline, and lifestyle details."
        )
    }

    user_parts = [
        f"Age: {age}",
        f"Gender: {gender}",
        f"Current weight: {current_weight_kg:.1f} kg",
        f"Desired weight: {desired_weight_kg:.1f} kg",
    ]
    if activity_level:
        user_parts.append(f"Activity level: {activity_level}")
    if goal_timeline:
        user_parts.append(f"Goal timeline: {goal_timeline}")
    if preferences:
        user_parts.append(f"Workout preferences: {preferences}")
    if injuries:
        user_parts.append(f"Injuries/limitations: {injuries}")
    if sleep_quality:
        user_parts.append(f"Sleep quality: {sleep_quality}")
    if tracking_calories is not None:
        user_parts.append(f"Tracks calories: {tracking_calories}")
    if notes:
        user_parts.append(f"Additional notes: {notes}")

    user_prompt = (
        "Generate an HTML-formatted, personalized fitness plan with two sections:<br>"
        "<b>Weekly Workout Schedule:</b> (with days and exercises, reps, durations) and "
        "<b>Sample Meal Plan:</b>. "
        "Tailor intensity to goal timeline and health data. Include safety tips and recovery guidance.<br>"
        + "<br>".join(user_parts)
    )

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role":"user","content":user_prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content

# ----------------------------
# PDF Creation
# ----------------------------
def create_pdf_with_workout(image_url, workout_plan_html):
    try:
        pdf = FPDF()
        pdf.add_page()

        # Background
        pdf.set_fill_color(240, 248, 255)
        pdf.rect(0, 0, 210, 297, 'F')

        # Title
        pdf.set_font("Helvetica", 'B', 18)
        pdf.set_text_color(25, 25, 112)
        pdf.cell(200, 12, txt="Your Fitness Goal & Workout Plan", ln=True, align='C')
        pdf.ln(5)

        # Divider
        pdf.set_draw_color(100, 149, 237)
        pdf.set_line_width(0.8)
        pdf.line(10, 25, 200, 25)
        pdf.ln(10)

        # Image
        img_data = requests.get(image_url).content
        with open("temp_image.jpg", "wb") as f:
            f.write(img_data)
        pdf.image("temp_image.jpg", x=30, w=150)
        pdf.ln(10)

        # Workout Plan Text
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=12)
        for line in workout_plan_html.replace("<br>", "\n").split("\n"):
            if line.strip().startswith("<b>"):
                pdf.set_font("Helvetica", 'B', 13)
            pdf.multi_cell(0, 8, line)

        # Footer
        pdf.ln(5)
        pdf.set_font("Helvetica", 'I', 10)
        pdf.set_text_color(105, 105, 105)
        pdf.cell(0, 10, txt="Generated by DayDream Forge", ln=True, align='C')

        # Upload PDF
        pdf_bytes = BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)

        upload_result = cloudinary_upload(
            file=pdf_bytes,
            folder="webhook_pdfs",
            resource_type="raw",
            public_id=f"fitness_plan_{int(time.time())}"
        )
        return upload_result.get("secure_url")

    except Exception as e:
        logging.error(f"❌ PDF creation/upload failed: {e}")
        return None

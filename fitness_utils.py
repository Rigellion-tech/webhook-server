import logging
import time
import re
from datetime import datetime
from io import BytesIO
import tempfile
import os
import requests
from fpdf import FPDF
from cloudinary.uploader import upload as cloudinary_upload
import cloudinary
import openai
from PIL import Image

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

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
    except Exception:
        return None


def get_field_value(fields, *label_keywords):
    for keyword in label_keywords:
        for field in fields:
            label = field.get('label', '').lower()
            if keyword.lower() not in label:
                continue
            raw = field.get('value')
            logging.info(f"🧩 Matching field '{label}' ➝ Raw value: {raw}")
            if isinstance(raw, list):
                first = raw[0] if raw else None
                if isinstance(first, dict):
                    return first.get('url') or first.get('text') or first.get('label') or str(first)
                if isinstance(first, str):
                    opts = field.get('options') or []
                    for opt in opts:
                        if opt.get('id') == first:
                            return opt.get('text') or opt.get('label') or first
                    return first
            if isinstance(raw, dict):
                return raw.get('text') or raw.get('label') or str(raw)
            if isinstance(raw, str):
                opts = field.get('options') or []
                for opt in opts:
                    if opt.get('id') == raw:
                        return opt.get('text') or opt.get('label') or raw
                return raw
            return str(raw)
    return None

# ----------------------------
# Workout Plan (GPT-Powered)
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
    notes=None,
    height_m=None
):
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
        f"Desired weight: {desired_weight_kg:.1f} kg"
    ]
    if height_m is not None:
        user_parts.insert(2, f"Height: {height_m:.2f} m")

    for label, value in [
        ("Activity level", activity_level),
        ("Goal timeline", goal_timeline),
        ("Workout preferences", preferences),
        ("Injuries/limitations", injuries),
        ("Sleep quality", sleep_quality),
        ("Tracks calories", tracking_calories),
        ("Additional notes", notes)
    ]:
        if value is not None:
            user_parts.append(f"{label}: {value}")

    user_prompt = (
        "Generate an HTML-formatted, personalized fitness plan with two sections:<br>"
        "<b>Weekly Workout Schedule:</b> (with days and exercises, reps, durations) and "
        "<b>Sample Meal Plan:</b>. Include safety tips and recovery guidance.<br>"
        + "<br>".join(user_parts)
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[system_msg, {"role": "user", "content": user_prompt}],
        temperature=0.7
    )
    plan = response.choices[0].message.content
    plan = re.sub(r"^```(?:html)?\n", "", plan)
    plan = re.sub(r"\n```$", "", plan)
    return plan

# ----------------------------
# PDF Creation: With Image
# ----------------------------
def create_pdf_with_workout(image_url, workout_plan_html):
    html = workout_plan_html.replace("’", "'").replace("“", '"').replace("”", '"')
    html = html.encode('latin-1', 'ignore').decode('latin-1')
    try:
        pdf = FPDF()
        pdf.add_page()
        # Header styling
        pdf.set_fill_color(240, 248, 255)
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_font("Helvetica", 'B', 18)
        pdf.set_text_color(25, 25, 112)
        pdf.cell(0, 12, txt="Your Fitness Goal & Workout Plan", ln=True, align='C')
        pdf.ln(5)
        pdf.set_draw_color(100, 149, 237)
        pdf.set_line_width(0.8)
        pdf.line(10, 25, 200, 25)
        pdf.ln(10)

        # Insert image (convert any format to JPEG)
        resp = requests.get(image_url)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        # Create a temp JPEG file
        tmp_img_dir = tempfile.gettempdir()
        tmp_img_path = os.path.join(tmp_img_dir, f"fit_img_{int(time.time())}.jpg")
        img.save(tmp_img_path, format="JPEG")
        pdf.image(tmp_img_path, x=30, w=150)
        os.remove(tmp_img_path)
        pdf.ln(10)

        # Render HTML content
        for line in html.split("<br>"):
            clean = re.sub(r"<[^>]+>", "", line)
            if not clean.strip():
                pdf.ln(5)
                continue
            # Bold headings
            if clean.strip().startswith("Weekly") or clean.strip().startswith("Sample"):
                pdf.set_font("Helvetica", 'B', 13)
            else:
                pdf.set_font("Helvetica", size=12)
            pdf.multi_cell(0, 8, clean)
        pdf.ln(5)

        # Footer
        pdf.set_font("Helvetica", 'I', 10)
        pdf.set_text_color(105, 105, 105)
        pdf.cell(0, 10, txt="Generated by DayDream Forge", ln=True, align='C')

        # Save to a guaranteed file path then upload
        tmp_pdf_dir = tempfile.gettempdir()
        tmp_pdf_path = os.path.join(tmp_pdf_dir, f"fitness_plan_{int(time.time())}.pdf")
        pdf.output(tmp_pdf_path)
        upload_res = cloudinary_upload(
            file=tmp_pdf_path,
            folder="webhook_pdfs",
            resource_type="raw",
            public_id=f"fitness_plan_{int(time.time())}"
        )
        os.remove(tmp_pdf_path)
        return upload_res.get("secure_url")

    except Exception as e:
        logging.error(f"❌ PDF creation/upload failed: {e}")
        return None

# ----------------------------
# PDF Creation: Plan Only
# ----------------------------
def create_pdf_plan_only(workout_plan_html):
    html = workout_plan_html.replace("’", "'").replace("“", '"').replace("”", '"')
    html = html.encode('latin-1', 'ignore').decode('latin-1')
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, txt="Personalized Workout Plan", ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Helvetica", size=12)
        for line in html.split("<br>"):
            clean = re.sub(r"<[^>]+>", "", line)
            if not clean.strip():
                pdf.ln(5)
                continue
            pdf.multi_cell(0, 8, clean)
        # Save and upload
        tmp_pdf_dir = tempfile.gettempdir()
        tmp_pdf_path = os.path.join(tmp_pdf_dir, f"plan_only_{int(time.time())}.pdf")
        pdf.output(tmp_pdf_path)
        upload_res = cloudinary_upload(
            file=tmp_pdf_path,
            folder="workout_plan_pdfs",
            resource_type="raw",
            public_id=f"plan_only_{int(time.time())}"
        )
        os.remove(tmp_pdf_path)
        return upload_res.get("secure_url")

    except Exception as e:
        logging.error(f"❌ Plan-only PDF creation failed: {e}")
        return None

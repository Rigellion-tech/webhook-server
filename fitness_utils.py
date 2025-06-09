import logging
import time
from datetime import datetime
from io import BytesIO
import requests
from fpdf import FPDF
from cloudinary.uploader import upload as cloudinary_upload

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

import logging

def get_field_value(fields, *label_keywords):
    for keyword in label_keywords:
        for field in fields:
            label = field.get('label', '').lower()
            value = field.get('value')

            if keyword.lower() in label:
                logging.info(f"🧩 Matching field '{label}' ➝ Raw value: {value}")

                if isinstance(value, list):
                    if value and isinstance(value[0], dict):
                        return value[0].get('url') or value[0].get('text') or value[0].get('label') or str(value[0])
                    elif value and isinstance(value[0], str):
                        return value[0]

                elif isinstance(value, dict):
                    return value.get('text') or value.get('label') or value.get('value') or str(value)

                elif isinstance(value, str):
                    return value

                # Fallback for unknown format
                return str(value)

        return None


def generate_workout_plan(age, gender, current_weight_kg, desired_weight_kg):
    try:
        weight_diff_kg = desired_weight_kg - current_weight_kg
        weight_diff_lbs = weight_diff_kg * 2.20462
        goal = "maintain"
        plan = []

        if weight_diff_lbs < -2:
            goal = "lose"
        elif weight_diff_lbs > 2:
            goal = "gain"

        plan.append(f"🎯 Goal: {goal.title()} {abs(round(weight_diff_lbs))} lbs")

        if gender:
            salutation = "Hey Queen" if gender.lower() == "female" else "Hey King"
        else:
            salutation = "Hey Champion"
        plan.insert(0, f"{salutation}, here’s your personalized workout plan:")

        # Weekly Schedule
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule = []
        for i, day in enumerate(days):
            if goal == "lose":
                if i % 2 == 0:
                    schedule.append(f"{day}: Cardio (30–45 min) + Core")
                else:
                    schedule.append(f"{day}: Strength (Full-body) or Active Rest")
            elif goal == "gain":
                if i % 3 == 0:
                    schedule.append(f"{day}: Push workout (Chest/Triceps)")
                elif i % 3 == 1:
                    schedule.append(f"{day}: Pull workout (Back/Biceps)")
                else:
                    schedule.append(f"{day}: Legs/Core")
            else:
                schedule.append(f"{day}: Balanced full-body training or light yoga")

        plan.append("<br><b>🗓️ Weekly Workout Schedule:</b>")
        plan.extend(schedule)

        # Meal Suggestions
        meals = [
            "🥗 Breakfast: Oats with berries and protein powder",
            "🍗 Lunch: Grilled chicken salad with quinoa",
            "🥑 Snack: Greek yogurt + almonds",
            "🍝 Dinner: Salmon with sweet potatoes and broccoli"
        ]

        if goal == "gain":
            meals.append("🍌 Extra: Peanut butter banana shake after dinner")
        elif goal == "lose":
            meals.append("🚫 Avoid: Sugary drinks, fried food, heavy sauces")

        plan.append("<br><br><b>🍽️ Sample Meal Plan:</b>")
        plan.extend(meals)

        if gender and gender.lower() == "female":
            plan.append("🔹 Emphasize glutes, legs, and core strength")
        elif gender and gender.lower() == "male":
            plan.append("🔹 Emphasize upper body, core, and functional lifts")

        if age and age > 40:
            plan += [
                "🔹 Add joint-friendly routines and longer warmups",
                "🔹 Prioritize recovery: sleep, hydration, mobility"
            ]

        plan.append("🔥 You got this. Let’s make it happen!")

        return "<br>".join(plan)
    except Exception as e:
        logging.error(f"❌ Workout plan generation failed ➝ {e}")
        return "No plan available."

def create_pdf_with_workout(image_url, workout_plan_html):
    try:
        pdf = FPDF()
        pdf.add_page()

        pdf.set_fill_color(240, 248, 255)
        pdf.rect(0, 0, 210, 297, 'F')

        pdf.set_font("Helvetica", 'B', 18)
        pdf.set_text_color(25, 25, 112)
        pdf.cell(200, 12, txt="Your Fitness Goal & Workout Plan", ln=True, align='C')
        pdf.ln(5)
        pdf.set_draw_color(100, 149, 237)
        pdf.set_line_width(0.8)
        pdf.line(10, 25, 200, 25)
        pdf.ln(10)

        img_data = requests.get(image_url).content
        with open("temp_image.jpg", "wb") as f:
            f.write(img_data)
        pdf.image("temp_image.jpg", x=30, w=150)
        pdf.ln(10)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=12)
        for line in workout_plan_html.replace("<br>", "\n").split("\n"):
            if line.strip().startswith("🔹"):
                pdf.set_text_color(70, 130, 180)
                pdf.set_font("Helvetica", style='B', size=11)
            elif line.strip().startswith("📄") or line.strip().startswith("🗓️") or line.strip().startswith("🍽️"):
                pdf.set_text_color(199, 21, 133)
                pdf.set_font("Helvetica", style='B', size=13)
            elif line.strip() == "":
                continue
            else:
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 8, line)

        pdf.ln(5)
        pdf.set_font("Helvetica", 'I', 10)
        pdf.set_text_color(105, 105, 105)
        pdf.cell(0, 10, txt="Generated by DayDream Forge", ln=True, align='C')

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

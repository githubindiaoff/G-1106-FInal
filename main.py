from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
import time
import io
import re
import pickle
import numpy as np
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import torch
import torch.nn as nn

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
CORS(app)

# --- MongoDB Setup ---
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["nutridb"]

# --- Model Loading ---
MODEL_PATH = "model/nutra_classifier_v1.pth"
SCALER_PATH = "model/scaler.pkl"

class NutraClassifier(nn.Module):
    def __init__(self, input_dim, num_classes):
        super(NutraClassifier, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes)
        )
    def forward(self, x):
        return self.network(x)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = NutraClassifier(input_dim=9, num_classes=4).to(device)
scaler = None

try:
    print(f"Loading local ANN model from: {MODEL_PATH}")
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True))
    model.eval()
    
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    print("Model and Scaler loaded successfully.")
except Exception as e:
    print(f"Warning: Failed to load local model/scaler: {e}")
    model = None

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    if not data or not data.get("mobileNumber") or not data.get("password"):
        return jsonify({"error": "Missing credentials"}), 400
    
    if db.users.find_one({"mobileNumber": data["mobileNumber"]}):
        return jsonify({"error": "User already exists with this mobile number."}), 409
        
    hashed_password = generate_password_hash(data["password"])
    db.users.insert_one({"mobileNumber": data["mobileNumber"], "password": hashed_password})
    return jsonify({"message": "User registered successfully"})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("mobileNumber") or not data.get("password"):
        return jsonify({"error": "Missing credentials"}), 400
        
    user = db.users.find_one({"mobileNumber": data["mobileNumber"]})
    if user and check_password_hash(user["password"], data["password"]):
        return jsonify({"message": "Login successful"})
        
    return jsonify({"error": "Invalid credentials or user not found."}), 401

@app.route("/predict", methods=["POST"])
def predict_deficiency():
    """
    Accepts clinical notes via `text` form field or lab reports via `file` upload.
    Extracts text locally using Pytesseract, and predicts using clinical_bert4.
    """
    try:
        age_str = request.form.get("age")
        if not age_str:
            return jsonify({"error": "Missing 'age'."}), 400
        age = int(age_str)
    except ValueError:
        return jsonify({"error": "Invalid 'age', must be an integer."}), 400

    gender = request.form.get("gender")
    condition = request.form.get("condition")
    text = request.form.get("text")
    file = request.files.get("file")
    
    extracted_text = ""

    # 1. Input Processing & OCR
    if file:
        try:
            # Read image bytes
            contents = file.read()
            
            if file.filename.lower().endswith('.pdf') or file.content_type == 'application/pdf':
                print("Converting PDF to images...")
                pages = convert_from_bytes(contents)
                extracted_text = ""
                for i, page in enumerate(pages):
                    print(f"Running OCR on page {i+1}...")
                    extracted_text += pytesseract.image_to_string(page) + "\n"
                print(f"OCR extracted text from PDF: {extracted_text[:100]}...")
            else:
                image = Image.open(io.BytesIO(contents))
                
                # Image preprocessing for better OCR (grayscale + upscale)
                image = image.convert('L')
                image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                
                # Run local OCR
                print("Running pytesseract OCR on uploaded image...")
                # Whitelist characters to numbers, letters, and basic punctuation to avoid things like AIS for 115
                config = r'-c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-: --psm 6'
                extracted_text = pytesseract.image_to_string(image, config=config)
                print(f"OCR extracted text: {extracted_text[:100]}...") # Print preview
        except Exception as e:
            return jsonify({"error": f"OCR Processing failed: {str(e)}"}), 400
    elif text:
        extracted_text = text
    else:
        return jsonify({"error": "Must provide either 'text' or 'file'"}), 400

    if not extracted_text.strip():
        extracted_text = "Empty sample submitted."

    # 2. Extract labs using regex
    # Added Q, D, and @ to handles slashed/dotted zeros in programming fonts
    patterns = {
        'ferritin': r"(Ferritin|Iron)\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)",
        'hgb': r"(Hemoglobin|HGB|Hb|Haemoglobin)\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)",
        'vit_d': r"(Vitamin[\s\-]*D|Vit[\s\-]*D|25-OH)\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)",
        'b12': r"(Cobalamin|B12|B1i2|Vit[\s\.\-]*B\w*?2|Vitamin[\s\.\-]*B\w*?2)\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)",
        'calcium': r"Calcium\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)",
        'folate': r"(Folate|Folic[\s]*Acid)\s*[:=\-]?\s*([0-9OoQqD@]+\.?[0-9OoQqD@]*)"
    }

    labs = {}
    clean_text = " ".join(extracted_text.split())
    # Log the full text extracted so you can see what OCR exactly caught in the terminal
    print(f"Full OCR Text Cleaned: {clean_text}")

    required_keys = ['ferritin', 'vit_d', 'b12', 'calcium']
    defaults = {'hgb': 14.0, 'folate': 10.0}
    
    missing_nutrients = []

    for key, pattern in patterns.items():
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            raw_val = match.group(match.lastindex)
            # Fix common OCR mistake where slashed/dotted zero is read as O, Q, D, or @
            clean_val = raw_val.upper().translate(str.maketrans('OQD@', '0000'))
            labs[key] = float(clean_val)
        elif key in required_keys:
            ui_names = {'ferritin': 'Iron', 'vit_d': 'Vitamin D', 'b12': 'Vitamin B12', 'calcium': 'Calcium'}
            missing_nutrients.append(ui_names.get(key, key))
        else:
            labs[key] = defaults.get(key, 0.0)

    if len(missing_nutrients) == 4:
         return jsonify({"error": "Invalid report: No nutrient values were detected! Please upload a valid laboratory report or clinical note."}), 400
    elif len(missing_nutrients) > 0:
         return jsonify({"error": f"Invalid report: Could not extract values for {', '.join(missing_nutrients)}. Ensure all 4 core nutrients are clearly visible."}), 400

    # 3. Local AI Classification
    predicted_label = "Unknown"
    if model and scaler:
        try:
            print("Running inference through local NutraClassifier model...")
            gender_enc = 1 if gender.upper() == 'M' else 0
            condition_map = {'Athlete': 0, 'Chronic Inflammation': 1, 'Normal': 2, 'Pregnant': 3, 'Smoker': 4}
            cond_enc = condition_map.get(condition, 2)
            
            raw_input = np.array([[age, gender_enc, cond_enc, labs['ferritin'], labs['hgb'],
                                   labs['vit_d'], labs['b12'], labs['calcium'], labs['folate']]])
            
            input_scaled = scaler.transform(raw_input)
            input_tensor = torch.FloatTensor(input_scaled).to(device)

            with torch.no_grad():
                logits = model(input_tensor)
                probs = torch.nn.functional.softmax(logits, dim=1)
                conf, pred_idx = torch.max(probs, dim=1)

            labels_map = {0: "Normal", 1: "Low", 2: "Serious", 3: "High"}
            predicted_label = labels_map.get(pred_idx.item(), "Unknown")
        except Exception as e:
            print(f"Inference error: {e}")
            predicted_label = "Error during classification"
    else:
        # Fallback if model loading failed during startup
        predicted_label = "Normal (Model not loaded)"

    # 4. Dynamic Response Marshalling
    
    is_deficient = predicted_label in ["Low", "Serious"]
    
    nutrient_val = "Severe Deficiency" if predicted_label == "Serious" else ("Mild Deficiency" if predicted_label == "Low" else "Normal")
    if predicted_label == "High":
        nutrient_val = "High/Abnormal"
        is_deficient = True
        
    ai_main_deficiency = "Nutrient Imbalance Detected" if is_deficient else "No Deficiency Detected"

    # Define thresholds
    ref_ranges = {
        'ferritin': 30.0,
        'hgb': 12.0 if gender.upper() == 'F' else 13.5,
        'vit_d': 20.0,
        'b12': 200.0,
        'calcium': 8.5,
        'folate': 4.8
    }
    
    def get_status(val, limit):
        if val < limit:
            if val < (limit * 0.7):
                return "Severe Deficiency"
            elif val < (limit * 0.9):
                return "Mild Deficiency"
            else:
                return "Slight Deficiency"
        return "Normal"

    # Evaluate individual statuses
    vit_d_status = get_status(labs['vit_d'], ref_ranges['vit_d'])
    b12_status = get_status(labs['b12'], ref_ranges['b12'])
    iron_status = get_status(labs['ferritin'], ref_ranges['ferritin'])
    calcium_status = get_status(labs['calcium'], ref_ranges['calcium'])

    # Re-evaluate overall deficiency based on actual calculated values to ensure accuracy
    all_statuses = [vit_d_status, b12_status, iron_status, calcium_status]
    has_deficiency = any(s != "Normal" for s in all_statuses)
    main_deficiency = "Nutrient Imbalance Detected" if has_deficiency else "No Deficiency Detected"

    # For general summary, we check what our model said, but for specific nutrients
    # we enforce the actual measured values instead of a blanket model fallback
    response = {
        "extracted_values": {
            "Vitamin D": f"{labs['vit_d']} ng/mL",
            "Vitamin B12": f"{labs['b12']} pg/mL",
            "Iron": f"{labs['ferritin']} ng/mL",  # Mapping Ferritin to Iron for UI
            "Calcium": f"{labs['calcium']} mg/dL",
        },
        "predicted_deficiency": main_deficiency,
        "nutrient_status": {
            "Vitamin D": vit_d_status,
            "Vitamin B12": b12_status,
            "Iron": iron_status,
            "Calcium": calcium_status
        }
    }

    return jsonify(response)

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(".", path)

if __name__ == "__main__":
    app.run(port=8000, debug=True)

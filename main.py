from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional
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

app = FastAPI(title="NutriDetector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/predict")
async def predict_deficiency(
    age: int = Form(...),
    gender: str = Form(...),
    condition: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Accepts clinical notes via `text` form field or lab reports via `file` upload.
    Extracts text locally using Pytesseract, and predicts using clinical_bert4.
    """
    
    extracted_text = ""

    # 1. Input Processing & OCR
    if file:
        try:
            # Read image bytes
            contents = await file.read()
            
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
                
                # Run local OCR
                print("Running pytesseract OCR on uploaded image...")
                extracted_text = pytesseract.image_to_string(image)
                print(f"OCR extracted text: {extracted_text[:100]}...") # Print preview
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"OCR Processing failed: {str(e)}")
    elif text:
        extracted_text = text
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'text' or 'file'")

    if not extracted_text.strip():
        extracted_text = "Empty sample submitted."

    # 2. Extract labs using regex
    patterns = {
        'ferritin': r"Ferritin.*?(\d+\.?\d*)",
        'hgb': r"(Hemoglobin|HGB).*?(\d+\.?\d*)",
        'vit_d': r"(Vitamin D|Vit D).*?(\d+\.?\d*)",
        'b12': r"(Cobalamin|B12).*?(\d+\.?\d*)",
        'calcium': r"Calcium.*?(\d+\.?\d*)",
        'folate': r"Folate.*?(\d+\.?\d*)"
    }

    labs = {}
    defaults = {'ferritin': 50.0, 'hgb': 14.0, 'vit_d': 35.0, 'b12': 400.0, 'calcium': 9.2, 'folate': 10.0}
    clean_text = " ".join(extracted_text.split())
    for key, pattern in patterns.items():
        match = re.search(pattern, clean_text, re.IGNORECASE)
        labs[key] = float(match.group(match.lastindex)) if match else defaults[key]

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
        
    main_deficiency = "Nutrient Imbalance Detected" if is_deficient else "No Deficiency Detected"

    # Define thresholds
    ref_ranges = {
        'ferritin': 30.0,
        'hgb': 12.0 if gender.upper() == 'F' else 13.5,
        'vit_d': 20.0,
        'b12': 200.0,
        'calcium': 8.5,
        'folate': 4.8
    }
    
    def get_status(val, limit, fallback):
        if val < limit:
            return "Severe Deficiency" if val < (limit * 0.7) else "Mild Deficiency"
        return fallback

    response = {
        "extracted_values": {
            "Vitamin D": f"{labs['vit_d']} ng/mL",
            "Vitamin B12": f"{labs['b12']} pg/mL",
            "Iron": f"{labs['ferritin']} ng/mL",  # Mapping Ferritin to Iron for UI
            "Calcium": f"{labs['calcium']} mg/dL",
        },
        "predicted_deficiency": main_deficiency,
        "nutrient_status": {
            "Vitamin D": get_status(labs['vit_d'], ref_ranges['vit_d'], nutrient_val),
            "Vitamin B12": get_status(labs['b12'], ref_ranges['b12'], nutrient_val),
            "Iron": get_status(labs['ferritin'], ref_ranges['ferritin'], nutrient_val),
            "Calcium": get_status(labs['calcium'], ref_ranges['calcium'], nutrient_val)
        }
    }

    return response

# Mount static files at the end so it doesn't override the /predict route
app.mount("/", StaticFiles(directory=".", html=True), name="static")

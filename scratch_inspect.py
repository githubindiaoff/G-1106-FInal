import joblib
import sys

try:
    med_enc = joblib.load('d:/pavithra/G-1106-FInal/model2/medication_encoder.pkl')
    print("Medications:", med_enc.classes_)
    
    target_enc = joblib.load('d:/pavithra/G-1106-FInal/model2/target_encoder.pkl')
    print("Targets:", target_enc.classes_)
    
    gender_enc = joblib.load('d:/pavithra/G-1106-FInal/model2/gender_encoder.pkl')
    print("Genders:", gender_enc.classes_)
except Exception as e:
    print("Error:", e)

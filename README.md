# Setup Guide for NutriDetector Project 
Any new developer downloading this code will need to perform the following steps to get the environment running:

### Step 1: Install Python Requirements
They will need Python installed. In the project directory, run:
```bash
pip install -r requirements.txt
```

### Step 2: Install and Start MongoDB
Because user authentication relies on a database, they must:
1. Download **MongoDB Community Server**.
2. Run the MongoDB daemon manually via terminal: `mongod` (or via Windows Services: `Start-Service MongoDB`).
3. Ensure it is accessible locally at `mongodb://localhost:27017/`.

### Step 3: Install Tesseract OCR
Your Python code hardcodes `tesseract.exe` to `C:\Program Files\Tesseract-OCR\tesseract.exe`, so anyone getting the repo must have it there:
1. Download the Tesseract-OCR installer for Windows.
2. Install it using the default path (`C:\Program Files\Tesseract-OCR`).

### Step 4: Run the App
With MongoDB and Tesseract properly mapped, start the Flask server:
```bash
python main.py
```
Then simply navigate to `http://localhost:8000` in the browser!
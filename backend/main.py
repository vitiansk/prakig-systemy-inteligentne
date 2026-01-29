from fastapi import FastAPI, UploadFile, File, HTTPException
from ultralytics import YOLO
import torch
import cv2
import numpy as np
import base64
import io
from datetime import datetime
from sqlalchemy.orm import Session

from lprnet_arch import LPRNet, CHARS, decode_lpr
from logic import ParkingSystem
from database import init_db, SessionLocal, ParkingSession

app = FastAPI(title="Parking Intelligence System API")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Inicjalizacja bazy danych przy starcie
try:
    init_db()
    print("Database initialized.")
except Exception as e:
    print(f"Error initializing DB: {e}")

# Wczytanie modeli AI
try:
    print(f"Loading models on {DEVICE}...")
    yolo = YOLO("/app/weights/best.pt")
    
    lpr = LPRNet(len(CHARS)).to(DEVICE)
    lpr.load_state_dict(torch.load("/app/weights/lprnet_best.pth", map_location=DEVICE))
    lpr.eval()
    print("Models loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR loading models: {e}")

parking = ParkingSystem()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend is running"}

# --- ENDPOINTY ZARZĄDZANIA ---

@app.get("/logs")
def get_logs():
    """Zwraca całą bazę danych (historię sesji)."""
    db = SessionLocal()
    try:
        logs = db.query(ParkingSession).order_by(ParkingSession.entry_time.desc()).all()
        return logs
    finally:
        db.close()

@app.post("/pay")
def pay_for_parking(data: dict):
    """Symuluje opłacenie parkingu dla danego numeru rejestracyjnego."""
    plate = data.get("plate")
    db = SessionLocal()
    try:
        session = db.query(ParkingSession).filter(
            ParkingSession.plate == plate, 
            ParkingSession.exit_time == None
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Nie znaleziono aktywnego pojazdu")
        
        # Calculate fee dynamically
        fee = parking.calculate_current_fee(session.entry_time)
        
        session.is_paid = True
        session.amount_due = fee
        db.commit()
        
        # Open gate on successful payment as requested
        parking.open_gate()
        
        return {"message": f"Opłacono postój dla {plate}. Bramka otwarta.", "amount": fee}
    finally:
        db.close()

@app.post("/force_exit")
def force_exit(data: dict):
    """Admin: Wymuszenie wyjazdu (Wypuść)."""
    plate = data.get("plate")
    msg = parking.force_exit(plate)
    return {"status": "ok", "message": msg}

@app.post("/manual_open")
def manual_open():
    """Ręczne otwarcie bramki."""
    msg = parking.manual_open()
    return {"status": "ok", "message": msg}

@app.post("/emergency_evacuation")
def emergency_evacuation():
    """Tryb awaryjny - otwarcie bramki."""
    msg = parking.emergency_evacuation()
    return {"status": "warning", "message": msg}

# --- GŁÓWNY SILNIK PRZETWARZANIA ---

@app.post("/process_frame")
async def process_frame(file: UploadFile = File(...), mode: str = "entry"):
    """
    Przetwarza zdjęcie z kamery:
    1. Wykrywa tablicę (YOLO).
    2. Rozpoznaje tekst (LPRNet).
    3. Zapisuje w bazie i zwraca dane wraz z wycinkiem zdjęcia (Base64).
    """
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results = yolo(img)
        detections = []
        message = "Brak wykrycia"
        open_barrier = False
        plate_base64 = None

        if results:
            for res in results:
                for box in res.boxes:
                    cls_id = int(box.cls[0])
                    if cls_id != 0: continue # Interesują nas tylko tablice

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Cropowanie z zabezpieczeniem krawędzi
                    crop = img[max(0, y1):min(img.shape[0], y2), max(0, x1):min(img.shape[1], x2)]
                    
                    if crop.size > 0:
                        # 1. Rozpoznawanie tekstu LPRNet
                        temp_img = cv2.resize(crop, (94, 24)).astype('float32')
                        temp_img = (temp_img - 127.5) * 0.0078125
                        temp_img = torch.from_numpy(temp_img).permute(2, 0, 1).unsqueeze(0).to(DEVICE)
                        
                        with torch.no_grad():
                            logits = lpr(temp_img)
                            plate_text = decode_lpr(logits)

                        # 2. Konwersja wycinka do Base64, aby wyświetlić go w przeglądarce
                        _, buffer = cv2.imencode('.jpg', crop)
                        plate_base64 = base64.b64encode(buffer).decode('utf-8')

                        # 3. Logika wjazdu/wyjazdu
                        if mode == "entry":
                            success, msg = parking.process_entry(plate_text)
                        else:
                            success, msg = parking.process_exit(plate_text)
                        
                        open_barrier = success
                        message = msg
                        detections.append({
                            "plate": plate_text, 
                            "box": [x1, y1, x2, y2],
                            "image": plate_base64
                        })

        return {
            "detections": detections, 
            "message": message, 
            "barrier": open_barrier, 
            "spots": parking.free_spots['A']
        }

    except Exception as e:
        print(f"Error processing frame: {e}")
        return {"error": str(e), "barrier": False}
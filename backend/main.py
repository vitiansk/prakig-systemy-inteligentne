from fastapi import FastAPI, UploadFile, File
from ultralytics import YOLO
import torch
import cv2
import numpy as np
from lprnet_arch import LPRNet, CHARS, decode_lpr
from logic import ParkingSystem

app = FastAPI()
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Wczytanie modeli (ścieżki dopasowane do Dockera)
try:
    print(f"Loading models on {DEVICE}...")
    yolo = YOLO("/app/weights/best.pt")
    
    lpr = LPRNet(len(CHARS)).to(DEVICE)
    lpr.load_state_dict(torch.load("/app/weights/lprnet_best.pth", map_location=DEVICE))
    lpr.eval()
    print("Models loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR loading models: {e}")
    # Nie przerywamy startu aplikacji, ale warto to logować
    # W produkcji aplikacja powinna prawdopodobnie się zrestartować

parking = ParkingSystem()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Parking MVP Backend is running. Go to http://localhost:8501 for the UI."}

@app.post("/process_frame")
async def process_frame(file: UploadFile = File(...), mode: str = "entry"):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results = yolo(img)
        detections = []
        message = "Oczekiwanie..."
        open_barrier = False
        spots = parking.free_spots['A']

        # Jeśli nic nie wykryto, zwracamy pusty wynik
        if not results:
             return {"detections": [], "message": message, "barrier": False, "spots": spots}

        for res in results:
            for box in res.boxes:
                # 1. Filtrowanie klasy: Przetwarzaj tylko klasę 0 (Tablica)
                cls_id = int(box.cls[0])
                if cls_id != 0:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Bezpieczne cropowanie
                if x1 < 0: x1 = 0
                if y1 < 0: y1 = 0
                if x2 > img.shape[1]: x2 = img.shape[1]
                if y2 > img.shape[0]: y2 = img.shape[0]
                
                crop_bgr = img[y1:y2, x1:x2]
                
                # Zgodnie z kodem użytkownika: używamy BGR (brak konwersji do RGB)
                # Ale zachowujemy debug
                cv2.imwrite("/app/images/debug_crop.jpg", crop_bgr)
                
                crop = crop_bgr
                
                plate_text = "UNKNOWN"
                
                # LPR Preprocessing (Zgodny z użytkownikiem)
                if crop.size > 0:
                    try:
                        # Resize (94, 24)
                        temp_img = cv2.resize(crop, (94, 24)).astype('float32')
                        # Normalize
                        temp_img = (temp_img - 127.5) * 0.0078125
                        # To Tensor [C, H, W]
                        # User code: torch.from_numpy(temp_img).permute(2, 0, 1).unsqueeze(0)
                        # temp_img shape here is [H, W, C]. permute(2,0,1) -> [C, H, W].
                        temp_img = torch.from_numpy(temp_img).permute(2, 0, 1).unsqueeze(0).to(DEVICE)
                        
                        with torch.no_grad():
                            logits = lpr(temp_img)
                            # Pass logits directly to decode_lpr (which is now updated)
                            plate_text = decode_lpr(logits)
                    except Exception as lpr_e:
                        print(f"Error in LPR: {lpr_e}")

                    # Logic execution
                    if mode == "entry":
                        success, msg = parking.process_entry(plate_text)
                    else:
                        success, msg = parking.process_exit(plate_text)
                    
                    # Update status for the first detected plate (assumption: 1 vehicle per frame)
                    open_barrier = success
                    message = msg
                    spots = parking.free_spots['A'] # Update spots count

                    detections.append({"plate": plate_text, "box": [x1, y1, x2, y2]})

        return {"detections": detections, "message": message, "barrier": open_barrier, "spots": spots}

    except Exception as e:
        print(f"Error processing frame: {e}")
        return {"detections": [], "message": f"Error: {str(e)}", "barrier": False, "spots": parking.free_spots['A']}
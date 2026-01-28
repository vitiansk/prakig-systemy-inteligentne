import streamlit as st
import requests
from PIL import Image
import io
import os
import cv2
import numpy as np

# Konfiguracja
BACKEND_URL = "http://backend:8000/process_frame"
IMAGE_FOLDER = "/app/images"

st.set_page_config(page_title="Parking MVP Operator Panel", layout="wide")

st.title("🚗 Inteligentny Parking - Panel Operatora")

# Sidebar
st.sidebar.header("Sterowanie")
mode = st.sidebar.radio("Tryb Kamery", ["Wjazd (Entry)", "Wyjazd (Exit)"])
mode_api = "entry" if "Wjazd" in mode else "exit"

# Ładowanie obrazów
if not os.path.exists(IMAGE_FOLDER):
    st.error(f"Katalog {IMAGE_FOLDER} nie istnieje!")
    image_files = []
else:
    image_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

selected_image = st.sidebar.selectbox("Wybierz obraz z kamery", image_files)

col1, col2 = st.columns(2)

if selected_image:
    image_path = os.path.join(IMAGE_FOLDER, selected_image)
    image = Image.open(image_path)
    
    with col1:
        st.subheader("Widok z kamery (Symulacja)")
        st.image(image, use_container_width=True)

    if st.button("📸 Przetwórz Obraz"):
        # Przygotowanie pliku do wysłania
        img_bytes = io.BytesIO()
        image.save(img_bytes, format=image.format)
        img_bytes = img_bytes.getvalue()

        files = {"file": ("image.jpg", img_bytes, "image/jpeg")}
        params = {"mode": mode_api}

        try:
            with st.spinner("Analiza obrazu..."):
                response = requests.post(BACKEND_URL, files=files, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Wizualizacja wyników
                detections = data.get("detections", [])
                message = data.get("message", "")
                barrier_open = data.get("barrier", False)
                spots = data.get("spots", "N/A")

                # Rysowanie ramek
                img_np = np.array(image)
                for det in detections:
                    box = det["box"]
                    plate = det["plate"]
                    
                    color = (0, 255, 0) if barrier_open else (255, 0, 0) # BGR for opencv
                    cv2.rectangle(img_np, (box[0], box[1]), (box[2], box[3]), color, 3)
                    cv2.putText(img_np, plate, (box[0], box[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                
                with col2:
                    st.subheader("Wyniki Analizy")
                    st.metric(label="Wolne Miejsca", value=spots)
                    
                    # Pobranie rozpoznanych tablic
                    plates_found = [d['plate'] for d in detections]
                    plates_text = ", ".join(plates_found) if plates_found else "Brak"
                    
                    if barrier_open:
                        st.success(f"✅ SZLABAN OTWARTY\n\n🆔 Tablica: **{plates_text}**\n\n📝 Komunikat: {message}")
                    else:
                        st.error(f"⛔ SZLABAN ZAMKNIĘTY\n\n🆔 Tablica: **{plates_text}**\n\n📝 Komunikat: {message}")
                    
                    st.image(img_np, caption="Wizualizacja Detekcji", use_container_width=True)
                    
            else:
                st.error(f"Błąd backendu: {response.status_code} - {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("Nie udało się połączyć z backendem. Czy kontener 'backend' działa?")
        except Exception as e:
            st.error(f"Wystąpił błąd: {e}")

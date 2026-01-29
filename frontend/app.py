import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import base64

st.set_page_config(page_title="Parking Intelligence System", layout="wide")
BACKEND_URL = "http://backend:8000"

st.title("🛡️ Inteligentny System Parkingowy")

# Zakładki dla lepszej organizacji
tab_camera, tab_active, tab_database, tab_super = st.tabs([
    "📸 Kamera i Rozpoznawanie", 
    "🚗 Obecnie na parkingu", 
    "📑 Pełna baza danych",
    "🦸 Super Parking (Admin)"
])

# ... (Camera code remains similar but I need to be careful with line offsets, I'll skip editing that block and target tabs definition first) ... 
# Wait, I must do replacement in chunks or logic. 
# Better strategy: Replace the tabs definition line, then append the new tab content at the end of file (or before database tab if structure permits).
# The file ends at line ~146. I will replace the tab definition first.

# --- ZAKŁADKA 1: KAMERA ---
# --- ZAKŁADKA 1: KAMERA ---
with tab_camera:
    col_input, col_output = st.columns(2)
    
    with col_input:
        st.subheader("Wejście")
        # Wybór trybu szlabanu
        gate_mode = st.radio("Wybierz bramkę:", ["Wjazd (Entry)", "Wyjazd (Exit)"], horizontal=True)
        mode_api = "entry" if "Wjazd" in gate_mode else "exit"
        
        uploaded_file = st.file_uploader("Wgraj zdjęcie z kamery", type=['jpg', 'jpeg', 'png'])
        
    with col_output:
        st.subheader("Wynik Rozpoznawania AI")
        if uploaded_file:
            if st.button("🚀 Przetwórz obraz"):
                files = {"file": uploaded_file.getvalue()}
                params = {"mode": mode_api}
                res = requests.post(f"{BACKEND_URL}/process_frame", files=files, params=params)
                
                if res.status_code == 200:
                    data = res.json()
                    detections = data.get("detections", [])
                    message = data.get("message", "")
                    
                    if detections:
                        first_det = detections[0]
                        plate_text = first_det.get("plate", "Brak odczytu")
                        st.success(f"Tekst tablicy: **{plate_text}**")
                        st.info(f"Komunikat systemu: {message}")
                        
                        # Wyświetlanie wycinka tablicy z bazy64
                        if "image" in first_det:
                            try:
                                img_data = base64.b64decode(first_det["image"])
                                st.image(img_data, caption="Wycinek rozpoznany przez LPRNet", width=300)
                            except Exception as e:
                                st.error(f"Błąd wyświetlania wycinka: {e}")
                    else:
                        st.warning("Nie wykryto żadnej tablicy.")
                else:
                    st.error("Błąd serwera AI")

# --- ZAKŁADKA 2: OBECNIE NA PARKINGU ---
# --- ZAKŁADKA 2: OBECNIE NA PARKINGU ---
with tab_active:
    st.subheader("Pojazdy znajdujące się wewnątrz obiektu")
    
    if st.button("🔄 Odśwież stan", key="refresh_active"):
        st.rerun()

    logs = requests.get(f"{BACKEND_URL}/logs").json()
    df = pd.DataFrame(logs)
    if not df.empty:
        # Filtrujemy tylko te, które nie mają czasu wyjazdu
        active_cars = df[df['exit_time'].isnull()].copy()
        
        if not active_cars.empty:
            # Obliczanie opłaty dla wyświetlania
            import datetime
            active_cars['entry_time'] = pd.to_datetime(active_cars['entry_time'])
            now = pd.Timestamp.now()
            
            # Funkcja pomocnicza do obliczania opłaty w DataFrame
            def calc_fee(entry_t):
                duration = now - entry_t
                hours = duration.total_seconds() / 3600
                import math
                billable = math.ceil(hours)
                if billable < 1: billable = 1
                return billable * 2.0

            active_cars['current_fee'] = active_cars['entry_time'].apply(calc_fee)

            # Wyświetlanie jako interaktywna tabela z przyciskami
            st.write("Lista pojazdów (Kliknij 'Opłać' aby uregulować należność):")
            
            for index, row in active_cars.iterrows():
                col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
                with col1:
                    st.write(f"🚗 **{row['plate']}**")
                with col2:
                    st.write(f"Wjazd: {row['entry_time'].strftime('%H:%M:%S')}")
                with col3:
                    if row['is_paid']:
                        st.success("Opłacono")
                    else:
                        st.warning(f"Do zapłaty: {row['current_fee']} PLN")
                with col4:
                    if not row['is_paid']:
                        if st.button(f"💸 Opłać", key=f"pay_{row['id']}"):
                            try:
                                pay_res = requests.post(f"{BACKEND_URL}/pay", json={"plate": row['plate']})
                                if pay_res.status_code == 200:
                                    st.success(f"Opłacono! Kwota: {pay_res.json()['amount']} PLN")
                                    st.rerun()
                                else:
                                    st.error("Błąd płatności")
                            except Exception as e:
                                st.error(f"Err: {e}")

        else:
            st.info("Parking jest pusty.")

# --- ZAKŁADKA 3: CAŁA BAZA DANYCH ---
with tab_database:
    st.subheader("Logi systemowe (Pełna historia)")
    if st.button("📂 Pobierz całą bazę"):
        logs = requests.get(f"{BACKEND_URL}/logs").json()
        df = pd.DataFrame(logs)
        if not df.empty:
            st.dataframe(df, use_container_width=True) # Interaktywna tabela
        else:
            st.warning("Baza danych jest pusta.")

# --- ZAKŁADKA 4: SUPER PARKING (ADMIN) ---
with tab_super:
    st.subheader("🦸 Panel Administratora - Zarządzanie Pojazdami")
    st.info("W tym panelu możesz wymusić wyjazd pojazdu (otwarcie bramki i usunięcie z listy aktywnych).")
    
    if st.button("🔄 Odśwież listę", key="refresh_super"):
        st.rerun()

    logs = requests.get(f"{BACKEND_URL}/logs").json()
    df = pd.DataFrame(logs)
    if not df.empty:
        active_cars = df[df['exit_time'].isnull()].copy()
        
        if not active_cars.empty:
            st.write("### Aktywne sesje:")
            
            for index, row in active_cars.iterrows():
                col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
                with col1:
                    st.write(f"🚗 **{row['plate']}**")
                with col2:
                    st.write(f"Wjazd: {row['entry_time']}")
                with col3:
                    if row['is_paid']:
                        st.success(f"Opłacono: {row['amount_due']} PLN")
                    else:
                        st.error(f"Nieopłacony")
                with col4:
                    if st.button(f"🚨 WYPUŚĆ", key=f"force_{row['id']}"):
                        try:
                            res = requests.post(f"{BACKEND_URL}/force_exit", json={"plate": row['plate']})
                            if res.status_code == 200:
                                st.success(f"{res.json()['message']}")
                                st.rerun()
                            else:
                                st.error("Błąd admina")
                        except Exception as e:
                            st.error(f"Err: {e}")
        else:
            st.success("Brak pojazdów na parkingu.")
    else:
        st.warning("Baza danych jest pusta.")
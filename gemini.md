# PROJEKT: Inteligentny System Parkingowy (MVP)

## 1. Cel Projektu
Budowa prototypu systemu (MVP) opartego na mikrousługach i Dockerze, który automatyzuje kontrolę dostępu do parkingu przy użyciu wizji komputerowej (Computer Vision). System symuluje działanie kamer CCTV, przetwarza obraz, rozpoznaje tablice rejestracyjne i steruje szlabanem.

## 2. Architektura Techniczna
Projekt składa się z dwóch kontenerów Docker zarządzanych przez docker-compose:

### A. Backend (Service: `backend`)
- **Technologia:** Python 3.9, FastAPI.
- **Rola:** "Mózg" systemu. Przyjmuje obrazy, wykonuje inferencję AI, podejmuje decyzje biznesowe.
- **Modele AI:**
  - Detekcja pojazdu/tablicy: YOLO (`best.pt`).
  - OCR (Odczyt znaków): LPRNet (`lprnet_best.pth`) - wymaga specyficznej definicji architektury sieci w kodzie (SmallBasicBlock).
- **Ścieżki:** Wagi znajdują się w `/app/weights`.

### B. Frontend (Service: `frontend`)
- **Technologia:** Python 3.9, Streamlit.
- **Rola:** "Panel Operatora". Symuluje kamerę (wysyła zdjęcia z folderu `/app/images` do backendu) i wizualizuje wyniki (ramki na obrazie, stan szlabanu, liczniki miejsc).
- **Komunikacja:** Wysyła żądania HTTP POST na adres `http://backend:8000/process_frame`.

## 3. Logika Biznesowa (Ontologia Parkingu)

### Pojęcia
- **Strefa A:** Główny obszar parkowania (pojemność startowa: 20 miejsc).
- **Szlaban:** Stan logiczny (OTWARTY/ZAMKNIĘTY).

### Reguły (Rules Engine)

#### Scenariusz 1: WJAZD (Entry)
1. Kamera wykrywa tablicę rejestracyjną.
2. System sprawdza dostępność miejsc w `Strefie A`.
   - JEŻELI `wolne_miejsca > 0`:
     - Zapisz `numer_rejestracyjny` i `czas_wjazdu` w Rejestrze Wjazdów.
     - Zmniejsz licznik wolnych miejsc o 1.
     - Decyzja: **OTWÓRZ SZLABAN**.
   - JEŻELI `wolne_miejsca == 0`:
     - Decyzja: **ZAMKNIJ SZLABAN** (Brak miejsc).

#### Scenariusz 2: WYJAZD (Exit)
1. Kamera wykrywa tablicę rejestracyjną.
2. System szuka tablicy w Rejestrze Wjazdów.
   - **Logika Rozmyta (Failsafe):** Użyj odległości Levenshteina (próg <= 2 znaki) do dopasowania odczytanej tablicy z tablicą w bazie (np. odczyt 'XYZ-123' pasuje do wpisu 'XYZ-I23').
3. Weryfikacja Płatności:
   - W MVP zakładamy symulację: Jeśli pojazd jest w rejestrze -> uznajemy, że opłacił/ma prawo wyjechać.
4. Akcja:
   - Usuń pojazd z Rejestru Wjazdów.
   - Zwiększ licznik wolnych miejsc o 1.
   - Decyzja: **OTWÓRZ SZLABAN**.

## 4. Wytyczne dla Generowania Kodu (Agent Rules)
1. **Bezpieczeństwo:** Zawsze używaj `try-except` przy ładowaniu modeli i obsłudze żądań sieciowych.
2. **Reprodukowalność:** Kod definicji modelu LPRNet musi być identyczny z tym użytym podczas treningu (zachowaj kolejność warstw i słownik `CHARS`).
3. **Docker:** Ścieżki do plików muszą być bezwzględne wewnątrz kontenera (np. `/app/weights/best.pt`), a nie lokalne.
4. **Wizualizacja:** Frontend musi wyraźnie pokazywać status: Zielona ramka = Wjazd dozwolony, Czerwona ramka = Zakaz.
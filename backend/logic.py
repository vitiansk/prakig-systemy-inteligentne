import datetime
import Levenshtein
import Mock.GPIO as GPIO
import os
from database import SessionLocal, ParkingSession

# Setup Mock GPIO
BARRIER_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BARRIER_PIN, GPIO.OUT)

class ParkingSystem:
    def __init__(self, capacity_a=20):
        self.capacity_a = capacity_a
        self.db = SessionLocal()
        # Initialize capacity check from DB (count active sessions)
        active_count = self.db.query(ParkingSession).filter(ParkingSession.exit_time == None).count()
        self.spots_taken = active_count

    @property
    def free_spots(self):
        # We return a dict to match original interface for now, or just logic
        # Original used self.free_spots['A'], let's keeping it compatible or dynamic
        return {'A': self.capacity_a - self.spots_taken}

    def open_gate(self):
        """Simulate opening the gate via GPIO."""
        print(" [GPIO] Triggering Barrier OPEN")
        GPIO.output(BARRIER_PIN, GPIO.HIGH)
        # In a real system you might wait and set LOW, or the driver handles it.
        # For mock/simulation we just leave it or toggle.
        # Let's toggle back to LOW to simulate a pulse if needed, or just leave HIGH ("Open")
        # For this demo, let's assume HIGH = Open command sent.

    def process_entry(self, plate, zone='A'):
        if self.free_spots['A'] > 0:
            # Check if car is already inside (safety check logic)
            active_session = self.db.query(ParkingSession).filter(
                ParkingSession.plate == plate, 
                ParkingSession.exit_time == None
            ).first()

            if not active_session:
                new_session = ParkingSession(plate=plate)
                self.db.add(new_session)
                self.db.commit()
                self.spots_taken += 1
                
                self.open_gate()
                return True, "Wjazd dozwolony"
            
            return True, "Pojazd już na parkingu"
        return False, "Brak miejsc"

    def calculate_current_fee(self, entry_time):
        """Calculate fee: 2 PLN per started hour."""
        now = datetime.datetime.now()
        duration = now - entry_time
        hours = duration.total_seconds() / 3600
        import math
        billable_hours = math.ceil(hours)
        if billable_hours < 1: billable_hours = 1 # Minimum 1 hour
        return billable_hours * 2.0

    def process_exit(self, plate):
        # Fuzzy search for active sessions
        active_sessions = self.db.query(ParkingSession).filter(ParkingSession.exit_time == None).all()
        
        found_session = None
        best_dist = 3 # threshold
        
        for sess in active_sessions:
            dist = Levenshtein.distance(plate, sess.plate)
            if dist <= 2 and dist < best_dist:
                found_session = sess
                best_dist = dist
        
        if found_session:
            # Check if paid
            if not found_session.is_paid:
                current_fee = self.calculate_current_fee(found_session.entry_time)
                return False, f"Brak opłaty! Należność: {current_fee} PLN. Proszę opłacić w kasie."

            # If paid, allow exit
            found_session.exit_time = datetime.datetime.now()
            self.db.commit()
            
            self.spots_taken -= 1
            self.open_gate()
            
            return True, f"Dziękujemy {found_session.plate}. Szerokiej drogi!"
            
        return False, "Bilet nieznaleziony"

    def manual_open(self):
        self.open_gate()
        return "Barrier manual open triggered"

    def force_exit(self, plate):
        """Forcefully release a vehicle (Admin/Super Parking)."""
        session = self.db.query(ParkingSession).filter(
            ParkingSession.plate == plate, 
            ParkingSession.exit_time == None
        ).first()

        if session:
            session.exit_time = datetime.datetime.now()
            # Mark as processed/released by admin, payment status unchanged (or set to True if policy requires)
            # For "Wypuść" we assume simply clearing it from active list.
            self.db.commit()
            self.spots_taken -= 1
            self.open_gate()
            return f"Wymuszono wyjazd dla {plate}. Bramka otwarta."
        
        return "Nie znaleziono pojazdu na parkingu."

    def emergency_evacuation(self):
        self.open_gate()
        # Logic: Could also open all sessions? For now just physical open.
        return "EVACUATION STARTED (Gate Opened)"
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
            # Calculate amount due (Mock logic: 5.0 per hour or fixed)
            # MVP: just set paid to True and amount to mockup
            found_session.exit_time = datetime.datetime.now()
            found_session.amount_due = 10.0 # Mock fee
            found_session.is_paid = True   # Auto-pay for MVP demo
            
            self.db.commit()
            
            self.spots_taken -= 1
            self.open_gate()
            
            return True, f"Dziękujemy {found_session.plate}. Kwota: {found_session.amount_due} PLN (Zapłacono)"
            
        return False, "Bilet nieznaleziony/nieopłacony"

    def manual_open(self):
        self.open_gate()
        return "Barrier manual open triggered"

    def emergency_evacuation(self):
        self.open_gate()
        # Logic: Could also open all sessions? For now just physical open.
        return "EVACUATION STARTED (Gate Opened)"
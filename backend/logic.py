import datetime
import Levenshtein

class ParkingSystem:
    def __init__(self, capacity_a=20):
        self.free_spots = {'A': capacity_a}
        self.entry_register = {} # tablica -> data
        self.payments = {} # tablica -> bool

    def process_entry(self, plate, zone='A'):
        # Prosta logika: jeśli są miejsca -> wpuść
        if self.free_spots[zone] > 0:
            if plate not in self.entry_register:
                self.entry_register[plate] = datetime.datetime.now()
                self.free_spots[zone] -= 1
                return True, "Wjazd dozwolony"
            return True, "Pojazd już na parkingu"
        return False, "Brak miejsc"

    def process_exit(self, plate):
        # Znajdź najbardziej podobną tablicę (failsafe)
        found = None
        for reg in self.entry_register:
            if Levenshtein.distance(plate, reg) <= 2:
                found = reg
                break
        
        if found:
            # Tu w MVP zakładamy, że każdy wyjazd jest "opłacony" dla demonstracji,
            # lub wymagamy symulacji płatności. Dla uproszczenia demo: OTWÓRZ.
            self.entry_register.pop(found)
            self.free_spots['A'] += 1
            return True, f"Dziękujemy {found}"
        return False, "Bilet nieznaleziony/nieopłacony"
import RPi.GPIO as GPIO
import time
import spidev
from datetime import datetime

# --- KONFIGURATION (Einfach hier Zeiten ändern) ---
MORGEN_START = "06:00"
MORGEN_ENDE  = "12:00"
ABEND_LIMIT_MIN = "20:00"
ABEND_LIMIT_MAX = "22:00"

# Schwellenwert: Wenn Lichtsensor über diesem Wert, bleibt Zimmerlicht AUS
HELLIGKEIT_SCHWELLE = 600 

# Pin-Belegung
SENSOR_POWER_PIN = 18
ZIMMER_LICHT_PIN = 24  # Pin für deine Wohnungsbeleuchtung
KNOPF_MANUELL_AUS = 25 # Ein physischer Knopf zum Ausschalten
# --------------------------------------------------

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_POWER_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ZIMMER_LICHT_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(KNOPF_MANUELL_AUS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

manuell_ausgeschaltet = False

def get_time_obj(time_str):
    return datetime.strptime(time_str, "%H:%M").time()

def get_analog_value(channel):
    GPIO.output(SENSOR_POWER_PIN, GPIO.HIGH)
    time.sleep(0.01)
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    GPIO.output(SENSOR_POWER_PIN, GPIO.LOW)
    return data

def steuerung_wohnung(lichtwert):
    global manuell_ausgeschaltet
    jetzt = datetime.now().time()
    
    # 1. Manueller Knopf-Check (Reset des Status um Mitternacht)
    if GPIO.input(KNOPF_MANUELL_AUS) == GPIO.LOW:
        manuell_ausgeschaltet = True
        print("Licht manuell ausgeschaltet.")

    if jetzt < get_time_obj("04:00"): # Reset-Logik für den nächsten Tag
        manuell_ausgeschaltet = False

    # 2. Zeitfenster Logik
    ist_morgens = get_time_obj(MORGEN_START) <= jetzt <= get_time_obj(MORGEN_ENDE)
    ist_abends = get_time_obj(ABEND_LIMIT_MIN) <= jetzt <= get_time_obj(ABEND_LIMIT_MAX)

    if not manuell_ausgeschaltet:
        if ist_morgens:
            # Wenn es morgens ist, aber draußen schon sehr hell: Licht aus
            if lichtwert > HELLIGKEIT_SCHWELLE:
                GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)
                print("Wohnung: Hell genug, Licht bleibt aus.")
            else:
                GPIO.output(ZIMMER_LICHT_PIN, GPIO.HIGH)
                print("Wohnung: Morgen-Beleuchtung aktiv.")
        
        elif ist_abends:
            # Abends einfach an (oder du fügst hier noch Lichtwert-Logik ein)
            GPIO.output(ZIMMER_LICHT_PIN, GPIO.HIGH)
            print("Wohnung: Abend-Beleuchtung aktiv.")
        
        else:
            GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)
    else:
        GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)

def garten_logik(wasserwert, lichtwert):
    # (Hier kommt dein Code vom vorherigen Schritt rein)
    if wasserwert > 750:
        print("Garten: Pumpe aktiv.")
        # GPIO.output(PUMP_RELAY_PIN, GPIO.HIGH)...
    
    # Rückgabe des Intervalls basierend auf Sonne
    return 3600 if lichtwert > 850 else 300 # Wir prüfen alle 5 Min für das Zimmerlicht!

try:
    print("Multi-System Online: Garten & Wohnung werden überwacht.")
    while True:
        w_wert = get_analog_value(0) # Wasser
        l_wert = get_analog_value(1) # Sonne
        
        # Beide Systeme nutzen den gleichen 'l_wert'
        steuerung_wohnung(l_wert)
        intervall = garten_logik(w_wert, l_wert)
        
        # Da das Zimmerlicht reaktionsschnell sein soll (z.B. wenn Wolken kommen),
        # setzen wir das Intervall hier fest auf 5 Minuten (300s), 
        # außer die Garten-Logik fordert eine noch schnellere Prüfung.
        time.sleep(min(intervall, 300))

except KeyboardInterrupt:
    GPIO.cleanup()

import RPi.GPIO as GPIO
import time
import spidev
from datetime import datetime, time as dt_time

# ========================== KONFIGURATION ==========================
# Zeitfenster
MORGEN_START = dt_time(6, 0)
MORGEN_ENDE  = dt_time(12, 0)
ABEND_START  = dt_time(20, 0)
ABEND_ENDE   = dt_time(22, 0)

# Schwellenwerte
HELLIGKEIT_SCHWELLE = 600      # Wenn höher → draußen hell genug
FEUCHTIGKEIT_SCHWELLE = 750    # Wenn höher → Boden zu trocken → Pumpe an

# Pins
SENSOR_POWER_PIN = 18
ZIMMER_LICHT_PIN = 24
PUMP_PIN         = 23          # Pumpe (Relay)
KNOPF_MANUELL_AUS = 25

# Intervall (Sekunden)
NORMAL_INTERVAL = 300          # 5 Minuten
# ==================================================================

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_POWER_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ZIMMER_LICHT_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PUMP_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(KNOPF_MANUELL_AUS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

manuell_ausgeschaltet = False
last_pump_time = 0

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

    # Manueller Knopf
    if GPIO.input(KNOPF_MANUELL_AUS) == GPIO.LOW:
        manuell_ausgeschaltet = True
        print(f"[{datetime.now()}] Licht manuell ausgeschaltet.")

    # Reset um 4 Uhr morgens
    if jetzt < dt_time(4, 0):
        manuell_ausgeschaltet = False

    if manuell_ausgeschaltet:
        GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)
        return

    ist_morgens = MORGEN_START <= jetzt <= MORGEN_ENDE
    ist_abends  = ABEND_START  <= jetzt <= ABEND_ENDE

    if ist_morgens:
        if lichtwert > HELLIGKEIT_SCHWELLE:
            GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)
            print(f"[{datetime.now()}] Morgen: Hell genug → Licht aus")
        else:
            GPIO.output(ZIMMER_LICHT_PIN, GPIO.HIGH)
            print(f"[{datetime.now()}] Morgen: Dunkel → Licht an")

    elif ist_abends:
        GPIO.output(ZIMMER_LICHT_PIN, GPIO.HIGH)
        print(f"[{datetime.now()}] Abend: Licht automatisch an")
    else:
        GPIO.output(ZIMMER_LICHT_PIN, GPIO.LOW)

def garten_logik(wasserwert, lichtwert):
    global last_pump_time
    jetzt = time.time()

    # Pumpe nur alle 30 Minuten max laufen lassen (Sicherheit)
    if wasserwert > FEUCHTIGKEIT_SCHWELLE and (jetzt - last_pump_time) > 1800:
        GPIO.output(PUMP_PIN, GPIO.HIGH)
        print(f"[{datetime.now()}] Garten: Pumpe AN (Feuchtigkeit {wasserwert})")
        time.sleep(8)                    # Pumpe 8 Sekunden laufen lassen
        GPIO.output(PUMP_PIN, GPIO.LOW)
        print(f"[{datetime.now()}] Garten: Pumpe AUS")
        last_pump_time = jetzt

    # Intervall anpassen je nach Helligkeit
    return 180 if lichtwert > 850 else 300   # 3 Min bei Sonne, 5 Min bei Bewölkung

# ========================== HAUPTSCHLEIFE ==========================
try:
    print("🌱 Multi-System gestartet: Garten + Wohnung")
    
    while True:
        wasserwert = get_analog_value(0)   # Kanal 0 = Wasser
        lichtwert  = get_analog_value(1)   # Kanal 1 = Licht

        steuerung_wohnung(lichtwert)
        intervall = garten_logik(wasserwert, lichtwert)

        time.sleep(intervall)

except KeyboardInterrupt:
    print("\nProgramm beendet.")
    GPIO.cleanup()
except Exception as e:
    print(f"Fehler: {e}")
    GPIO.cleanup()

import network
from umqtt.simple import MQTTClient
from machine import Pin, PWM
import neopixel
from time import sleep, ticks_ms, ticks_diff
import _thread
import urandom

# Pin Configuration
LED_PIN = 15  # Pin for LED strip
BUZZER_PIN = Pin(4, Pin.OUT)  # Using a different pin for buzzer to avoid conflict
NUM_LEDS = 10

# Initialize LED strip
np = neopixel.NeoPixel(Pin(LED_PIN), NUM_LEDS)

# MQTT Configuration
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_CLIENT_ID = ""

# MQTT Topics
LED_TOPICS = [f"cfga/led{i+1}{color}" for i in range(NUM_LEDS) for color in "rva"]
TOPIC_TIRA_COMPLETA = "cfga/tiraCompleta"
TOPIC_FUNCIONALIDAD = "cfga/funcionalidad"
TOPIC_CANCIONES = "cfga/canciones"

# Global Variables
led_colores = [(0, 0, 0)] * NUM_LEDS
led_sliders = [(0, 0, 0)] * NUM_LEDS
funcionalidad_activa = 0
tira_apagada = False  # Changed to False to start with animation
is_playing_music = False
last_message_time = 0
DEFAULT_TIMEOUT = 60000  # 1 minute in milliseconds
in_default_mode = True  # Start in default mode

# Music Notes and Songs
NOTES = {
    'D': 588, 'E': 660, 'B': 494, 'G': 784, 'F#': 740, 'C': 522, 'A': 440,
    'A_high': 880, 'C_high': 1046, 'F': 698, 'G_high': 784, 'B_high': 988,
    'D_low': 294, 'E_low': 330, 'F_low': 349, 'G_low': 392, 'C#': 554
}

# LED Functions
def random_color():
    return (urandom.randint(0, 255), urandom.randint(0, 255), urandom.randint(0, 255))

def check_timeout():
    global in_default_mode, funcionalidad_activa
    while True:
        current_time = ticks_ms()
        if not in_default_mode and ticks_diff(current_time, last_message_time) > DEFAULT_TIMEOUT:
            print("Timeout reached, switching to default mode")
            in_default_mode = True
            funcionalidad_activa = 0
        sleep(1)

def default_animation():
    global in_default_mode, tira_apagada
    while True:
        if in_default_mode and not tira_apagada:
            for i in range(NUM_LEDS):
                np[i] = random_color()
            np.write()
            sleep(0.5)
        sleep(0.1)

def inicializar_leds():
    global in_default_mode, tira_apagada
    in_default_mode = True
    tira_apagada = False
    _thread.start_new_thread(default_animation, ())
    _thread.start_new_thread(check_timeout, ())

def conectar_wifi():
    print("Conectando a WiFi...", end="")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    try:
        sta_if.connect('iPhone de Noe', '123412345')
        attempts = 0
        while not sta_if.isconnected() and attempts < 10:
            print(".", end="")
            sleep(0.3)
            attempts += 1
        
        if not sta_if.isconnected():
            print("\nNo se pudo conectar al WiFi. Continuando en modo por defecto...")
            return False
            
        print("\nWiFi Conectada!")
        return True
    except:
        print("\nError al conectar al WiFi. Continuando en modo por defecto...")
        return False

def parpadeo():
    global tira_apagada, in_default_mode
    while funcionalidad_activa == 1 and not tira_apagada and not in_default_mode:
        for i in range(NUM_LEDS):
            np[i] = led_sliders[i]
        np.write()
        sleep(0.3)
        np.fill((0, 0, 0))
        np.write()
        sleep(0.3)

def en_serie():
    global tira_apagada, in_default_mode
    while funcionalidad_activa == 2 and not tira_apagada and not in_default_mode:
        for i in range(NUM_LEDS):
            np.fill((0, 0, 0))
            np[i] = led_sliders[i]
            np.write()
            sleep(0.1)

def estatico():
    global tira_apagada, in_default_mode
    while funcionalidad_activa == 3 and not tira_apagada and not in_default_mode:
        for i in range(NUM_LEDS):
            np[i] = led_sliders[i]
        np.write()
        sleep(1)

# Music Functions
def play_note(pwm, frequency, duration):
    if frequency > 0:
        pwm.freq(frequency)
        pwm.duty(512)
        sleep(duration)
        pwm.duty(0)
        sleep(0.05)

def play_song_1():
    """Melodía de 'Cumpleaños Feliz'"""
    global is_playing_music
    is_playing_music = True
    pwm = PWM(BUZZER_PIN)
    
    song = [
        (NOTES['D_low'], 500), (NOTES['D_low'], 500),  # Cum-ple
        (NOTES['E_low'], 1000),                        # años
        (NOTES['D_low'], 1000),                        # Fe
        (NOTES['G_low'], 1000),                        # liz
        (NOTES['F_low'], 2000),                        # _
        (NOTES['D_low'], 500), (NOTES['D_low'], 500),  # Cum-ple
        (NOTES['E_low'], 1000),                        # años
        (NOTES['D_low'], 1000),                        # Fe
        (NOTES['A'], 1000),                            # liz
        (NOTES['G'], 2000),                            # _
        (NOTES['D_low'], 500), (NOTES['D_low'], 500),  # Cum-ple
        (NOTES['D'], 1000),                            # años
        (NOTES['B'], 1000),                            # que
        (NOTES['G_low'], 1000),                        # ri
        (NOTES['F_low'], 1000),                        # do
        (NOTES['E_low'], 2000),                        # _
        (NOTES['C'], 500), (NOTES['C'], 500),          # Cum-ple
        (NOTES['B'], 1000),                            # años
        (NOTES['G_low'], 1000),                        # Fe
        (NOTES['A'], 1000),                            # liz
        (NOTES['G'], 2000),                            # _
    ]
    
    for note, duration in song:
        if not is_playing_music:
            break
        play_note(pwm, note, duration/1000)
    
    pwm.deinit()
    is_playing_music = False

def play_song_2():
    """Rudolph the Red-Nosed Reindeer - Nueva versión"""
    global is_playing_music
    is_playing_music = True
    pwm = PWM(BUZZER_PIN)
    
    song = [
        # Verso 1
        (NOTES['D'], 500), (NOTES['E'], 500),         # Ru-dolph
        (NOTES['D'], 300), (NOTES['B'], 500),         # the red
        (NOTES['G'], 700), (NOTES['E'], 500),         # nosed rein
        (NOTES['D'], 1000),                           # deer
        (NOTES['D'], 300), (NOTES['E'], 300),         # had a
        (NOTES['D'], 300), (NOTES['E'], 300),         # ve-ry
        (NOTES['D'], 700), (NOTES['G'], 700),         # shi-ny
        (NOTES['F#'], 1200),                          # nose
        
        # Verso 2
        (NOTES['C'], 500), (NOTES['D'], 500),         # and if
        (NOTES['C'], 300), (NOTES['A'], 500),         # you ev-er
        (NOTES['F#'], 700), (NOTES['E'], 500),        # saw it
        (NOTES['D'], 1000),                           # glow
        (NOTES['D'], 300), (NOTES['E'], 300),         # you would
        (NOTES['D'], 300), (NOTES['E'], 300),         # e-ven
        (NOTES['D'], 700), (NOTES['E'], 700),         # say it
        (NOTES['D'], 1000),                           # glows
        
        # Verso 3
        (NOTES['E'], 500), (NOTES['E'], 500),         # all of
        (NOTES['G'], 500), (NOTES['E'], 500),         # the other
        (NOTES['D'], 700), (NOTES['B'], 500),         # rein-deer
        (NOTES['D'], 1000),                           # used to
        (NOTES['C'], 500), (NOTES['E'], 500),         # laugh and
        (NOTES['D'], 500), (NOTES['C'], 500),         # call him
        (NOTES['B'], 1200),                           # names
        
        # Final
        (NOTES['A'], 500), (NOTES['B'], 500),         # they
        (NOTES['D'], 500), (NOTES['E'], 500),         # ne-ver
        (NOTES['F#'], 500), (NOTES['F#'], 500),       # let poor
        (NOTES['F#'], 1000),                          # Ru-dolph
        (NOTES['G'], 500), (NOTES['G'], 500),         # join in
        (NOTES['F#'], 500), (NOTES['E'], 500),        # a-ny
        (NOTES['D'], 500), (NOTES['C'], 500),         # rein-deer
        (NOTES['A'], 1000),                           # games!
    ]
    
    for note, duration in song:
        if not is_playing_music:
            break
        play_note(pwm, note, duration/1000)
    
    pwm.deinit()
    is_playing_music = False

def play_song_3():
    """Jingle Bell Rock - Nueva versión"""
    global is_playing_music
    is_playing_music = True
    pwm = PWM(BUZZER_PIN)
    
    song = [
        # Intro
        (NOTES['D'], 300), (NOTES['D'], 300),         # Jin-gle
        (NOTES['D'], 700),                            # Bell
        (NOTES['C#'], 300), (NOTES['C#'], 300),       # Jin-gle
        (NOTES['C#'], 700),                           # Bell
        (NOTES['B'], 300), (NOTES['C#'], 300),        # Jin-gle
        (NOTES['B'], 700),                            # Bell
        (NOTES['F#'], 500),                           # Rock
        
        # Verso 1
        (NOTES['B'], 300), (NOTES['C#'], 300),        # Jin-gle
        (NOTES['B'], 700),                            # Bells
        (NOTES['F#'], 500),                           # Swing
        (NOTES['A'], 300),                            # and
        (NOTES['B'], 300), (NOTES['C#'], 300),        # Jin-gle
        (NOTES['B'], 700),                            # Bells
        (NOTES['G'], 500),                            # Ring
        
        # Puente
        (NOTES['E'], 500), (NOTES['F#'], 500),        # Snow-ing
        (NOTES['F#'], 300),                           # and
        (NOTES['A'], 500), (NOTES['B'], 500),         # blow-ing
        (NOTES['A'], 300),                            # up
        (NOTES['E'], 500), (NOTES['F#'], 500),        # bush-els
        (NOTES['G'], 300),                            # of
        (NOTES['A'], 700),                            # fun
        
        # Estribillo
        (NOTES['B'], 500),                            # Now
        (NOTES['A'], 300),                            # the
        (NOTES['B'], 500), (NOTES['A'], 500),         # jin-gle
        (NOTES['B'], 300),                            # hop
        (NOTES['B'], 500),                            # has
        (NOTES['E'], 500), (NOTES['E'], 500),         # be-gun!
        
        # Final
        (NOTES['D'], 300), (NOTES['D'], 300),         # Jin-gle
        (NOTES['D'], 700),                            # Bell
        (NOTES['C#'], 300), (NOTES['C#'], 300),       # Jin-gle
        (NOTES['C#'], 700),                           # Bell
        (NOTES['B'], 300), (NOTES['C#'], 300),        # Jin-gle
        (NOTES['B'], 700),                            # Bell
        (NOTES['F#'], 500),                           # Rock!
    ]
    
    for note, duration in song:
        if not is_playing_music:
            break
        play_note(pwm, note, duration/1000)
    
    pwm.deinit()
    is_playing_music = False

def stop_music():
    global is_playing_music
    is_playing_music = False
    BUZZER_PIN.value(0)

# MQTT Message Handler
def llegada_mensaje(topic, msg):
    global led_colores, led_sliders, funcionalidad_activa, tira_apagada, is_playing_music, last_message_time, in_default_mode
    topic_str = topic.decode()
    msg_str = msg.decode()
    print(f"Mensaje en tópico {topic_str}: {msg_str}")
    
    # Update last message time
    last_message_time = ticks_ms()

    try:
        # LED Control
        if topic_str == TOPIC_FUNCIONALIDAD:
            funcionalidad_activa = int(msg_str)
            tira_apagada = False
            in_default_mode = False
            
            if funcionalidad_activa == 1:
                _thread.start_new_thread(parpadeo, ())
            elif funcionalidad_activa == 2:
                _thread.start_new_thread(en_serie, ())
            elif funcionalidad_activa == 3:
                _thread.start_new_thread(estatico, ())

        elif topic_str.startswith("cfga/led"):
            led_index = int(topic_str.split('/')[-1][3:-1]) - 1
            color_channel = topic_str[-1]
            value = int(msg_str)

            if 0 <= led_index < NUM_LEDS and 0 <= value <= 255:
                r, g, b = led_colores[led_index]
                sr, sg, sb = led_sliders[led_index]

                if color_channel == 'r':
                    r, sr = value, value
                elif color_channel == 'v':
                    g, sg = value, value
                elif color_channel == 'a':
                    b, sb = value, value

                led_colores[led_index] = (r, g, b)
                led_sliders[led_index] = (sr, sg, sb)
                np[led_index] = (r, g, b)
                np.write()

        elif topic_str == TOPIC_TIRA_COMPLETA:
            if msg_str == "1":
                tira_apagada = False
                in_default_mode = False
                for i in range(NUM_LEDS):
                    np[i] = led_colores[i]
                np.write()
            elif msg_str == "0":
                tira_apagada = True
                np.fill((0, 0, 0))
                np.write()

        # Music Control
        elif topic_str == TOPIC_CANCIONES:
            stop_music()  # Stop any currently playing song
            sleep(0.1)  # Small delay to ensure clean transition
            
            if msg_str == "1":
                _thread.start_new_thread(play_song_1, ())
            elif msg_str == "2":
                _thread.start_new_thread(play_song_2, ())
            elif msg_str == "3":
                _thread.start_new_thread(play_song_3, ())
            elif msg_str == "0":  # Add stop functionality
                stop_music()

    except Exception as e:
        print("Error procesando mensaje:", e)

def subscribir():
    try:
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.set_callback(llegada_mensaje)
        client.connect()

        # Subscribe to all LED topics
        for topic in LED_TOPICS:
            client.subscribe(topic)
        
        # Subscribe to control topics
        client.subscribe(TOPIC_TIRA_COMPLETA)
        client.subscribe(TOPIC_FUNCIONALIDAD)
        client.subscribe(TOPIC_CANCIONES)

        print(f"Conectado a {MQTT_BROKER}")
        return client
    except:
        print("Error al conectar al broker MQTT")
        return None

# Main Initialization
def main():
    inicializar_leds()  # This now starts the default animation immediately
    if conectar_wifi():
        client = subscribir()
        if client:
            while True:
                try:
                    client.wait_msg()
                except:
                    print("Error de conexión. Continuando en modo por defecto...")
                    break
    
    # Keep the program running with default animation
    while True:
        sleep(1)

if __name__ == "__main__":
    main()
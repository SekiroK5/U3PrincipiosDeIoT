from machine import Pin, I2C, SoftSPI, PWM
import framebuf
import time
import network
from umqtt.simple import MQTTClient
import _thread
import random
import json
import dht

# Constants for MAX7219
_MAX7219_NOOP = 0
_MAX7219_DIGIT0 = 1
_MAX7219_DECODEMODE = 9
_MAX7219_INTENSITY = 10
_MAX7219_SCANLIMIT = 11
_MAX7219_SHUTDOWN = 12
_MAX7219_DISPLAYTEST = 15

# Constants for SSD1306
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xa4)
SET_NORM_INV = const(0xa6)
SET_DISP = const(0xae)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xa0)
SET_MUX_RATIO = const(0xa8)
SET_COM_OUT_DIR = const(0xc0)
SET_DISP_OFFSET = const(0xd3)
SET_COM_PIN_CFG = const(0xda)
SET_DISP_CLK_DIV = const(0xd5)
SET_PRECHARGE = const(0xd9)
SET_VCOM_DESEL = const(0xdb)
SET_CHARGE_PUMP = const(0x8d)

class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.poweron()
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,
            SET_MEM_ADDR, 0x00,
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xf1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xff,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_framebuf()

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.buffer = bytearray(((height // 8) * width) + 1)
        self.buffer[0] = 0x40
        self.framebuf = framebuf.FrameBuffer1(memoryview(self.buffer)[1:], width, height)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_framebuf(self):
        self.i2c.writeto(self.addr, self.buffer)

    def poweron(self):
        pass

class MAX7219Display:
    def __init__(self, spi, cs, width=32, height=8):
        self.spi = spi
        self.cs = cs
        self.width = width
        self.height = height
        self.buffer = bytearray(height * width // 8)
        self.fb = framebuf.FrameBuffer(self.buffer, width, height, framebuf.MONO_HLSB)
        self.init_display()

    def init_display(self):
        commands = [
            (_MAX7219_SHUTDOWN, 0),
            (_MAX7219_DISPLAYTEST, 0),
            (_MAX7219_SCANLIMIT, 7),
            (_MAX7219_DECODEMODE, 0),
            (_MAX7219_SHUTDOWN, 1),
            (_MAX7219_INTENSITY, 8),
        ]
        for cmd, data in commands:
            self.write_all(cmd, data)

    def write_all(self, command, data):
        self.cs.off()
        for _ in range(self.width // 8):
            self.spi.write(bytearray([command, data]))
        self.cs.on()

    def show(self):
        for y in range(self.height):
            self.cs.off()
            for x in range(self.width // 8):
                index = x + y * (self.width // 8)
                self.spi.write(bytearray([_MAX7219_DIGIT0 + y, self.buffer[index]]))
            self.cs.on()

    def text(self, text, x, y):
        self.fb.text(text, x, y, 1)

    def fill(self, color):
        self.fb.fill(color)

class RGBLed:
    def __init__(self, red_pin, green_pin, blue_pin):
        self.red = PWM(Pin(red_pin))
        self.green = PWM(Pin(green_pin))
        self.blue = PWM(Pin(blue_pin))
        
        for pin in (self.red, self.green, self.blue):
            pin.freq(1000)
        
        self.is_on = True
        self.christmas_mode = False
        self.christmas_step = 0
        self.last_update = time.time()
        self.luminance = 255
        self.temp_control_active = False
        self.last_temp_blink = time.time()
        self.temp_led_state = True

    def set_color(self, r, g, b):
        if not self.is_on:
            for pin in (self.red, self.green, self.blue):
                pin.duty(0)
            return
        
        r = int(r * self.luminance / 255)
        g = int(g * self.luminance / 255)
        b = int(b * self.luminance / 255)
        
        self.red.duty(int(r * 1023 / 255))
        self.green.duty(int(g * 1023 / 255))
        self.blue.duty(int(b * 1023 / 255))

    def update_temp_control(self, temp):
        if not (self.temp_control_active and self.is_on) or self.christmas_mode:
            return
            
        current_time = time.time()
        if current_time - self.last_temp_blink >= 0.5:
            self.last_temp_blink = current_time
            self.temp_led_state = not self.temp_led_state
            
            if self.temp_led_state:
                self.set_color(0, 255, 0) if temp < 30 else self.set_color(255, 0, 0)
            else:
                self.set_color(0, 0, 0)

    def set_temp_control(self, state):
        self.temp_control_active = state
        if not state:
            self.set_color(0, 0, 0)

    def set_power(self, state):
        self.is_on = state
        if not state:
            self.set_color(0, 0, 0)

    def set_christmas_mode(self, state):
        self.christmas_mode = state
        if not state:
            self.set_color(0, 0, 0)

    def set_luminance(self, luminance):
        self.luminance = max(0, min(255, luminance))

    def update_christmas_pattern(self):
        if not (self.christmas_mode and self.is_on):
            return
            
        current_time = time.time()
        if current_time - self.last_update < 0.5:
            return
            
        self.last_update = current_time
        
        patterns = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (255, 195, 0),  # White
            (18, 182, 140)  # Custom pattern
        ]
        
        self.set_color(*patterns[self.christmas_step])
        self.christmas_step = (self.christmas_step + 1) % len(patterns)

class SnowAnimation:
    def __init__(self, oled1, oled2):
        self.oled1 = oled1
        self.oled2 = oled2
        self.snowflake_shapes = [
            [(0, 0), (1, -1), (-1, 1)],
            [(0, 0), (1, -1), (1, 0), (1, 1), (-1, -1), (-1, 0), (-1, 1)],
            [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        ]
        self.snowflakes = self.init_snowflakes()
        self.force_message = False
        self.displays_on = True
        self.last_switch = time.time()

    def init_snowflakes(self):
        return [{'x': random.randint(0, 127),
                'y': random.randint(0, 63),
                'shape': random.choice(self.snowflake_shapes),
                'size': random.randint(1, 2)} for _ in range(20)]

    def draw_snowflakes(self, oled):
        if not self.displays_on:
            oled.fill(0)
            oled.show()
            return
            
        oled.fill(0)
        for flake in self.snowflakes:
            for dx, dy in flake['shape']:
                oled.framebuf.fill_rect(
                    flake['x'] + dx * flake['size'],
                    flake['y'] + dy * flake['size'],
                    flake['size'], flake['size'], 1
                )
        oled.show()

    def draw_christmas_message(self, oled):
        if not self.displays_on:
            oled.fill(0)
            oled.show()
            return
            
        oled.fill(0)
        oled.text("!Feliz", 40, 20)
        oled.text("Navidad!", 35, 35)
        oled.show()

    def set_display_state(self, state):
        self.displays_on = state
        if not state:
            self.oled1.fill(0)
            self.oled2.fill(0)
            self.oled1.show()
            self.oled2.show()

    def set_message_state(self, state):
        self.force_message = state

    def update(self):
        if not self.displays_on:
            return

        current_time = time.time()
        show_message = self.force_message or (current_time - self.last_switch >= 30)
        
        if current_time - self.last_switch >= 30 and not self.force_message:
            self.last_switch = current_time

        if show_message:
            self.draw_christmas_message(self.oled1)
            self.draw_christmas_message(self.oled2)
        else:
            for flake in self.snowflakes:
                flake['y'] += flake['size']
                if flake['y'] > 63:
                    flake['y'] = 0
                    flake['x'] = random.randint(0, 127)
            
            self.draw_snowflakes(self.oled1)
            self.draw_snowflakes(self.oled2)

class ScrollingText:
    def __init__(self, max7219):
        self.max7219 = max7219
        self.text = "Arriba la UTNG"
        self.offset = 0
        self.lock = _thread.allocate_lock()

    def update_text(self, new_text):
        with self.lock:
            self.text = new_text

    def scroll(self):
        while True:
            with self.lock:
                current_text = self.text
            
            self.max7219.fill(0)
            self.max7219.text(current_text, -self.offset, 0)
            self.max7219.show()
            
            self.offset += 1
            if self.offset >= len(current_text) * 8:
                self.offset = 0
            
            time.sleep(0.1)

def wifi_connect(ssid, password):
    print("Conectando a WiFi...")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.connect(ssid, password)
    while not sta_if.isconnected():
        time.sleep(0.1)
    print("WiFi Conectada!")

def main():
    # Initialize OLED displays
    i2c1 = I2C(0, scl=Pin(22), sda=Pin(21))
    i2c2 = I2C(1, scl=Pin(19), sda=Pin(17))
    oled1 = SSD1306_I2C(128, 64, i2c1)
    oled2 = SSD1306_I2C(128, 64, i2c2)
    
    # Initialize MAX7219
    spi = SoftSPI(sck=Pin(18), mosi=Pin(23), miso=Pin(14))
    cs = Pin(5, Pin.OUT)
    max7219 = MAX7219Display(spi, cs)
    
    # Initialize RGB LED
    rgb_led = RGBLed(25, 26, 27)
    
    # Initialize DHT sensor
    dht_sensor = dht.DHT11(Pin(4))
    
    # Initialize animations
    snow = SnowAnimation(oled1, oled2)
    scroller = ScrollingText(max7219)
    
    # Connect to WiFi
    wifi_connect('iPhone de Noe', '123412345')
    
    # Start scrolling text in a separate thread
    _thread.start_new_thread(scroller.scroll, ())
    
    # MQTT setup
    def mqtt_callback(topic, msg):
        topic = topic.decode()
        try:
            if topic == "cfga/oled":
                scroller.update_text(msg.decode())
            elif topic == "cfga/display/message":
                snow.set_message_state(json.loads(msg.decode()))
            elif topic == "cfga/display/power":
                snow.set_display_state(json.loads(msg.decode()))
            elif topic == "cfga/rgb/power":
                rgb_led.set_power(json.loads(msg.decode()))
            elif topic == "cfga/rgb/red" and json.loads(msg.decode()):
                rgb_led.set_christmas_mode(False)
                rgb_led.set_temp_control(False)
                rgb_led.set_color(255, 0, 0)
            elif topic == "cfga/rgb/green" and json.loads(msg.decode()):
                rgb_led.set_christmas_mode(False)
                rgb_led.set_temp_control(False)
                rgb_led.set_color(0, 255, 0)
            elif topic == "cfga/rgb/blue" and json.loads(msg.decode()):
                rgb_led.set_christmas_mode(False)
                rgb_led.set_temp_control(False)
                rgb_led.set_color(0, 0, 255)
            elif topic == "cfga/rgb/christmas":
                state = json.loads(msg.decode())
                rgb_led.set_christmas_mode(state)
                if state:
                    rgb_led.set_temp_control(False)
            elif topic == "cfga/rgb/luminance":
                rgb_led.set_luminance(json.loads(msg.decode()))
            elif topic == "cfga/rgb/temp_control":
                state = json.loads(msg.decode())
                rgb_led.set_temp_control(state)
                if state:
                    rgb_led.set_christmas_mode(False)
        except Exception as e:
            print(f"Error processing message: {e}")

    client = MQTTClient("DisplayAndLEDClient", "broker.emqx.io", port=1883)
    client.set_callback(mqtt_callback)
    client.connect()
    
    topics = [
        "cfga/oled",
        "cfga/display/message",
        "cfga/display/power",
        "cfga/rgb/power",
        "cfga/rgb/red",
        "cfga/rgb/green",
        "cfga/rgb/blue",
        "cfga/rgb/christmas",
        "cfga/rgb/luminance",
        "cfga/rgb/temp_control"
    ]
    
    for topic in topics:
        client.subscribe(topic)
    
    last_temp_read = 0
    temp = 0
    
    while True:
        current_time = time.time()
        if current_time - last_temp_read >= 2:
            try:
                dht_sensor.measure()
                temp = dht_sensor.temperature()
                last_temp_read = current_time
            except Exception as e:
                print(f"Error reading temperature: {e}")
        
        snow.update()
        rgb_led.update_christmas_pattern()
        rgb_led.update_temp_control(temp)
        client.check_msg()
        time.sleep(0.1)

if __name__ == '__main__':
    main()
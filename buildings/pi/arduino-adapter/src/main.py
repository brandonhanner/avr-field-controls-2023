import mqtt_client
from pysm import State, StateMachine, Event
from threading import Lock, Thread
import netifaces as ni
import serial
from typing import Union, List
import json
import libregpio as GPIO
import random


class LePotatoRelayModule(object):
    def __init__(self):
        self.channels: List[GPIO.OUT] = []
        # channel 1
        self.channels.append(GPIO.OUT("GPIOX_17"))
        # channel 2
        self.channels.append(GPIO.OUT("GPIOX_18"))
        # channel 3
        self.channels.append(GPIO.OUT("GPIOX_6"))
        # channel 4
        self.channels.append(GPIO.OUT("GPIOX_2"))
        # channel 5
        self.channels.append(GPIO.OUT("GPIOX_7"))
        # channel 6
        self.channels.append(GPIO.OUT("GPIOX_3"))
        # channel 7
        self.channels.append(GPIO.OUT("GPIOX_4"))
        # channel 8
        self.channels.append(GPIO.OUT("GPIOX_5"))

    def open_relay(self, relay):
        # convert the human intent of channel 1 into 0 index
        relay -= 1
        if relay >= 0 and relay <= (len(self.channels) - 1):
            self.channels[relay].high()

    def close_relay(self, relay):
        # convert the human intent of channel 1 into 0 index
        relay -= 1
        if relay >= 0 and relay <= (len(self.channels) - 1):
            self.channels[relay].low()


class ArduinoAdapter(object):
    def __init__(self, config_file):

        self.config_file = config_file

        self.mqtt_client: mqtt_client.MQTTClient

        self.ser_connection:serial.Serial
        self.serial_port = "dev/ttyAML0"
        self.ser_lock = Lock()

        self.id = ""
        self.interface = "eth0"

        self.relays = LePotatoRelayModule()

        self.heater_channel = 1 #default, will be overridden by config
        self.light_channel = 2 #default, will be overridden by config

        #################### S T A T E  M A C H I N E   S T U F F ####################
        self.sm_lock = Lock()

        self.sm = StateMachine("adapter")

        self.init_state = State("init_state")
        self.init_state.handlers = {
            "enter": self.init_state_job,
        }

        self.provisioning_state = State("provisioning_state")
        self.provisioning_state.handlers = {"enter": self.provision_state_job}

        self.run_state = State("run_state")
        self.run_state_thread: Thread
        self.run_state_stop: bool = False
        self.run_state.handlers = {"enter": self.run_state_job}

        self.sm.add_state(self.init_state, initial=True)
        self.sm.add_state(self.provisioning_state)
        self.sm.add_state(self.run_state)

        self.sm.add_transition(
            self.init_state, self.provisioning_state, "needs_provisioning_event"
        )

        self.sm.add_transition(self.init_state, self.run_state, "ready_to_run_event")
        self.sm.add_transition(
            self.provisioning_state, self.run_state, "ready_to_run_event"
        )

        self.sm.add_transition(self.provisioning_state, self.init_state, "reset_event")
        self.sm.add_transition(self.run_state, self.init_state, "reset_event")

        ##############################################################################

    def init_state_job(self, state, event):

        # read the config file
        with open(self.config_file, "r") as file:
            self.config = json.load(file)

        # see if the config file has an alternate config for the mqtt broker
        # if not use defaults
        mqtt_broker = self.config.get("mqtt_broker", "192.168.1.100")
        self.mqtt_client = mqtt_client.MQTTClient(mqtt_broker, 1883)
        self.mqtt_client.start_threaded()

        self.heater_channel = self.config.get("heater_channel", self.heater_channel)
        self.light_channel = self.config.get("light_channel", self.light_channel)

        self.serial_port = self.config.get("serial_port", self.serial_port)
        self.ser_connection = serial.Serial(self.serial_port, 115200, timeout=1.0)
        self.ser_connection.reset_input_buffer()

        self.interface = self.config.get("interface", self.interface)

        # see if the config file has a configured identity already
        # if not, send off to provisioning
        id = self.config.get("id", None)

        if id is None:
            self.sm.dispatch(Event("needs_provisioning_event"))
        else:
            self.id = id
            self.sm.dispatch(Event("ready_to_run_event"))

    def run_state_enter(self):
        self.run_state_thread = Thread(target=self.run_state_job, args=())
        self.run_state_thread.start()

    def run_state_job(self):

        self.run_state_stop = False

        self.mqtt_client.register_callback(f"{self.id}/relay/set", self.relay_commands)
        self.mqtt_client.register_callback(
            f"{self.id}/progress_bar/set", self.led_commands
        )

        while True:
            data = ""
            # see if there are any incoming bytes
            if self.ser_connection.in_waiting > 0:
                # and block until we get a terminating char
                self.ser_lock.acquire()
                data = self.ser_connection.readline().decode("utf-8").rstrip()
                self.ser_lock.release()

            # if there is a new message, handle it
            if data == "laser":
                self.mqtt_client.publish(
                    f"{self.id}/events/laser_detector/", {"event_type": "hit"}
                )
            elif data == "ball":
                self.mqtt_client.publish(
                    f"{self.id}/events/ball_detector/", {"event_type": "hit"}
                )
            if self.run_state_stop == True:
                break

    def run_state_exit(self):
        if self.run_state_thread.is_alive():
            self.run_stop = True
            self.run_state_thread.join()

    def relay_commands(self, topic: str, msg: dict):
        channel = msg.get("channel", None)
        state = msg.get("state", None)

        relay = None
        if channel == "heater":
            relay = self.heater_channel
        elif channel == "light":
            relay = self.light_channel
        elif isinstance(channel, int):
            if channel >0 and channel <= len(self.relays.channels):
                relay = channel

        if state == "on" and relay is not None:
            self.relays.close_relay(relay)
        elif state == "off" and relay is not None:
            self.relays.open_relay(relay)

    def led_commands(self, topic: str, msg: dict):
        pixel_data = msg.get("pixel_data", None)
        if pixel_data is not None:
            pixel_cmd = ""
            for index, pixel in enumerate(pixel_data):
                r = pixel[0]
                g = pixel[1]
                b = pixel[2]

                pixel_str = f"{r},{g},{b}"

                if index == 0:
                    pixel_cmd += pixel_str
                else:
                    pixel_cmd += "/" + pixel_str

            pixel_cmd += "\n"

            self.ser_lock.acquire()
            self.ser_connection.write(pixel_cmd.encode("utf-8"))
            self.ser_lock.release()

    def get_ip(self):
        interfaces = ni.interfaces()
        if self.interface in interfaces:
            ip = ni.ifaddresses(self.interface)[ni.AF_INET][0]['addr']
            return ip
        else:
            return None

    def provision_state_job(self):
        ip_addr = self.get_ip()

        #generate the pixel pattern to show
        colors = ["r", "g", "b"]
        pattern = []

        #create a 5 pixel pattern
        pattern.append("bl")
        for i in range(0,3):
            if ip_addr is not None:
                pattern.append(random.choice(colors))
            else:
                pattern.append("w")
        pattern.append("bl")

        #propogate that pattern 6 times to fill 30 pixels
        pixel_data = []
        for i in range(0,6):
            for entry in pattern:
                if entry == "r":
                    pixel_data.append([255,0,0])
                elif entry == "g":
                    pixel_data.append([0,255,0])
                elif entry == "b":
                    pixel_data.append([0,0,255])
                elif entry == "bl":
                    pixel_data.append([0,0,0])
                elif entry == "w":
                    pixel_data.append([255,255,255])

        #render the pattern
        self.led_commands("", {"pixel_data": pixel_data})

        #tell mqtt what the pattern is
        self.mqtt_client.publish(f"field/discovery/", {"pattern": pattern, "ip_addr": ip_addr})


if __name__ == "__main__":
    adapter = ArduinoAdapter(config_file="/app/configs/config.json")

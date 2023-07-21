import paho.mqtt.client as mqtt
from typing import Any, Union, List
from loguru import logger
import json
import re
import threading
from colored import fore, back, style
import traceback

class MQTTClient(object):
    def __init__(self, host="mqtt", port=1883):
        # mqtt
        self.mqtt_host = host
        self.mqtt_port = port

        self.mqtt_client = mqtt.Client()

        self.mqtt_client.on_connect = self.on_connect  # type:ignore
        self.mqtt_client.on_message = self.on_message

        self.topic_map = {}

    def run(self):
        # allows for graceful shutdown of any child threads
        self.mqtt_client.connect(host=self.mqtt_host, port=self.mqtt_port, keepalive=60)
        self.mqtt_client.loop_forever()

    def start_threaded(self):
        mqtt_thread = threading.Thread(target=self.run, args=())
        mqtt_thread.start()

    def register_callback(self, topic, function):
        if topic in self.topic_map.keys():
            logger.warning(f"EP: *****WARNING***** a callback is already registered for topic: {topic}")
        self.topic_map[topic] = function
        if self.mqtt_client.is_connected():
            self.mqtt_client.subscribe(topic)

    def publish(self, topic: str, message: Union[dict, List[dict]]):
        self.mqtt_client.publish(topic, json.dumps(message))

    def on_message(
        self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage
    ) -> None:
        try:
            # logger.debug(f"{msg.topic}: {str(msg.payload)}")
            payload = json.loads(msg.payload)
            self.handle_message(msg.topic, payload)
        except Exception as e:
            logger.debug(f"{fore.RED}Error handling message on {msg.topic}{style.RESET}")  # type: ignore
            logger.debug(traceback.format_exc())

    def on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int,
        properties: mqtt.Properties = None,  # type: ignore
    ) -> None:
        logger.debug(f" EP: Connected with result code {str(rc)}")
        for topic in self.topic_map.keys():
            logger.debug(f"MQTT: Subscribing to {topic}")
            client.subscribe(topic=topic)

    def handle_message(self, topic: str, msg: dict):
       #try the exact match way first
        handler = self.topic_map.get(topic, None)
        if handler is not None:
            handler(topic, msg)
        else:
            for map_topic, function in self.topic_map.items():
                if self.is_topic_match(topic, map_topic):
                    #we found a match!
                    function(topic, msg)

    def is_topic_match(self, topic: str, subscribed_topic: str):
        '''
        thanks chatgpt
        '''
        # Escape special characters in the subscribed_topic
        escaped_subscribed_topic = re.escape(subscribed_topic)

        # Replace '+' wildcard with the equivalent regular expression pattern
        escaped_subscribed_topic = escaped_subscribed_topic.replace(r'\+', r'[^/]+')

        # Replace '#' wildcard with the equivalent regular expression pattern
        escaped_subscribed_topic = escaped_subscribed_topic.replace(r'\#', r'.*')

        # Create the regular expression pattern
        pattern = f'^{escaped_subscribed_topic}$'

        # Perform regular expression matching
        if re.match(pattern, topic):
            return True
        else:
            return False

    def is_connected(self):
        return self.mqtt_client.is_connected()
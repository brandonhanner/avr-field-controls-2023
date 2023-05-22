import influxdb_client
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import paho.mqtt.client as mqtt
from typing import Any
from loguru import logger
import json
import os
import threading
import time
from colored import fore, back, style
from queue import Queue

# start
# create a queue
# create db and table and connect (as a thread)
# connect to mqtt and create callbacks (as a thread)

# start listening to mqtt
# everytime a new event comes in, format it and append to queue
# every x seconds, pull everything from the queue and commit all events to database


class EventProcessor(object):
    def __init__(self):
        # influxDB
        self.db_frequency = (
            1  # how often should we check the queue to commit to DB in Hz?
        )
        self.influx_client = InfluxDBClient(url='http://influxdb:8086', username='admin', password='bellavr23', org='avr')
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.buckets_api = self.influx_client.buckets_api()

        # shared
        self.shared_queue = Queue()

        # mqtt
        self.mqtt_host = "mqtt"
        self.mqtt_port = 1883

        self.mqtt_client = mqtt.Client()

        self.mqtt_client.on_connect = self.on_connect  # type:ignore
        self.mqtt_client.on_message = self.on_message

    def start(self):
        self.setup_db()
        influx_thread = threading.Thread(target=self.run_influx, args=())
        influx_thread.start()

        mqtt_thread = threading.Thread(target=self.run_mqtt, args=())
        mqtt_thread.start()

    ###################################################################################
    ################################  i n f l u x D B  ################################
    ###################################################################################
    def setup_db(self):
        not_init = True
        while not_init:
            res = self.influx_client.ping()
            if res:
                not_init = False
            time.sleep(1)
        logger.debug("EP: Connected to Database")
        logger.debug("EP: Checking for avr bucket...")

        bucket_init = False
        buckets = self.buckets_api.find_buckets().buckets
        for bucket in buckets:
            #logger.debug(f" ---\n ID: {bucket.id}\n Name: {bucket.name}\n Retention: {bucket.retention_rules}")
            if bucket.name == "avr":
                bucket_init = True
        if bucket_init:
            logger.debug("EP: avr bucket found!!!")
        else:
            raise Exception("avr bucket cant be found, check influx config!")

    def run_influx(self):
        while True:
            if not self.shared_queue.empty():
                updates = []
                # pull everything from the queue and put into a list
                while not self.shared_queue.empty():
                    update = self.shared_queue.get()
                    updates.append(update)
                if len(updates) > 1:
                    self.write_api.write(bucket='avr', record=updates)
                    # commit the list to the influxDB client
            time.sleep(1 / self.db_frequency)

    ###################################################################################
    ####################################  M Q T T  ####################################
    ###################################################################################

    def on_message(
        self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage
    ) -> None:
        try:
            logger.debug(f"{msg.topic}: {str(msg.payload)}")
            payload = json.loads(msg.payload)
            self.handle_event(msg.topic, payload)
        except Exception as e:
            logger.debug(f"{fore.RED}Error handling message on {msg.topic}{style.RESET}")  # type: ignore

    def on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int,
        properties: mqtt.Properties = None,  # type: ignore
    ) -> None:
        logger.debug(f" EP: Connected with result code {str(rc)}")
        client.subscribe(topic='+/events/#')

    def handle_event(self, topic: str, msg: dict):

        parts = topic.split("/")
        source = parts[0]
        # see if the source is a building
        if source in ["RTO", "RBO", "RTM", "RBM", "RTI", "RBI"]:
            subsystem = parts[2]
            
        # or the UI
        elif source == "ui":
            pass

    def run_mqtt(self):
        # allows for graceful shutdown of any child threads
        self.mqtt_client.connect(host=self.mqtt_host, port=self.mqtt_port, keepalive=60)
        self.mqtt_client.loop_forever()

if __name__ == "__main__":
    processor = EventProcessor()
    processor.start()

from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS, WriteType
from datetime import datetime
from mqtt_client import MQTTClient
from typing import Any
from loguru import logger
import threading
import time
from queue import Queue

# start
# create a queue
# create db and table and connect (as a thread)
# connect to mqtt and create callbacks (as a thread)

# start listening to mqtt
# everytime a new event comes in, format it and append to queue
# every x seconds, pull everything from the queue and commit all events to database
BUILDINGS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]

class EventProcessor(object):
    def __init__(self):
        # influxDB
        self.db_frequency = (
            1  # how often should we check the queue to commit to DB in Hz?
        )
        self.influx_client = InfluxDBClient(url='http://influxdb:8086', username='admin', password='bellavr23', org='avr')
        self.buckets_api = self.influx_client.buckets_api()

        # shared
        self.shared_queue = Queue()

        # mqtt
        self.mqtt_client = MQTTClient("mqtt", 1883)
        self.mqtt_client.register_callback('+/events/#', self.handle_event)
        self.mqtt_client.register_callback('+/commands/#', self.handle_command)

        self.event_id = 0

    def start(self):
        self.mqtt_client.start_threaded()
        self.setup_db()
        self.run_influx()

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
                    # logger.debug("Pulling an item from the queue!!!")
                    updates.append(update)
                if len(updates) >= 1:
                    logger.debug(f"Processing {len(updates)} updates to the DB!!!")
                    # logger.debug(updates)
                    with self.influx_client.write_api(write_options=WriteOptions(write_type=WriteType.batching, batch_size=len(updates))) as write_api:
                        write_api.write(bucket='avr', org="bell-avr", record=updates)
                    updates.clear()
            time.sleep(1 / self.db_frequency)

    ###################################################################################
    ###############################  C A L L B A C K S  ###############################
    ###################################################################################


    def handle_event(self, topic: str, msg: dict):
        parts = topic.split("/")
        source = parts[0]
        subsystem = parts[2]
        # see if the source is a building
        if source in BUILDINGS:
            if subsystem in ["laser_detector", "relay", "ball_detector", "led_bar"]:
                # logger.debug(f"EP: Building {source} received a {subsystem} event!")
                #create the influxDB item
                point = (
                    Point("events")
                    .tag("entity", source)
                    .tag("subsystem", subsystem)
                    .tag("type", msg["event_type"])
                    .field("timestamp", time.time_ns())
                    .field("id", self.event_id)
                    .time(time.time_ns()) #type: ignore
                    )
                # logger.debug("Pushing an item into the queue!!!")
                self.shared_queue.put(point)
                self.event_id += 1
        elif source == "ui":
            pass
        else:
            logger.warning(f"Received a message that doesnt fit the datamodel {topic}{msg}")

    def handle_command(self, topic: str, msg: dict):
        logger.debug("THE COMMAND CALLBACK WORKS!!!")

if __name__ == "__main__":
    processor = EventProcessor()
    processor.start()

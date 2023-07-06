import match
import mqtt_client
import time
from loguru import logger

def mapRange(value, inMin, inMax, outMin, outMax):
    return outMin + (((value - inMin) / (inMax - inMin)) * (outMax - outMin))

class Controller(object):
    def __init__(self):

        self.fire_buildings = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F"
        ]

        self.heater_buildings = [
            "G",
            "H",
            "I"
        ]

        #create an MQTT client
        self.mqtt_client = mqtt_client.MQTTClient("mqtt", 1883)
        self.mqtt_client.register_callback('+/events/#', self.handle_events)

        #create a match
        self.match = match.MatchModel(self.fire_buildings, self.heater_buildings)

    def handle_events(self, topic: str, msg: dict):
        parts = topic.split("/")
        source = parts[0]
        subsystem = parts[2]
        # see if the source is a building
        if source in (self.fire_buildings + self.heater_buildings):
            if subsystem in ["laser_detector","ball_detector"]:
                event_type = msg.get("event_type", None)
                if event_type == "hit":
                    self.match.fire_buildings[source].douse_fire()
        elif source == "ui":
            event_type = msg.get("event_type", None)
            if event_type is not None:
                self.match.dispatch(event_type)

    def run(self):
        self.mqtt_client.start_threaded()
        while True:
            # publish score
            current_score = self.match.calculate_score()
            self.mqtt_client.publish("ui/state/score", {"current_score": current_score})

            table_data = []
            for building_name, building in self.match.fire_buildings.items():
                row_data = {}
                row_data["building"] = building_name
                state = building.sm.state.name

                if state == "idle_state":
                    state = "Idle"
                elif state == "on_fire_state":
                    state = "Burning"
                elif state == "extinguished_state":
                    state = "Extinguished"

                row_data["state"] = state

                row_data["fire_level"] = mapRange(building.current_fire_level, 0, 16, 0, 100)
                row_data["score"] = building.score
                table_data.append(row_data)

            self.mqtt_client.publish("ui/state/table_data", table_data)

            # publish the states
            state = self.match.sm.state.name #type: ignore
            if state == "phase_1_state":
                state = "Phase 1"
            elif state == "phase_2_state":
                state = "Phase 2"
            elif state == "phase_3_state":
                state = "Phase 3"
            elif state == "idle_state":
                state = "Idle"
            elif state == "staging_state":
                state = "Staging/Preheat"
            elif state == "post_match_state":
                state = "End Game"
            self.mqtt_client.publish("ui/state/match_state", {"state":state})

            #publish the hot spot building
            self.mqtt_client.publish("ui/state/hotspot_building", {"building": self.match.random_hotspot_building})

            #publish time remainings
            time_left = time.strftime("%M:%S", time.gmtime(self.match.phase_timer.time_remaining))
            self.mqtt_client.publish("ui/state/phase_remaining", {"time": time_left})

            time_left = time.strftime("%M:%S", time.gmtime(self.match.match_timer.time_remaining))
            self.mqtt_client.publish("ui/state/match_remaining", {"time": time_left})

            time.sleep(.5)


if __name__ == "__main__":
    controller = Controller()
    controller.run()
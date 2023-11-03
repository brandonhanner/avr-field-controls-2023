import match
import mqtt_client
import time
from loguru import logger


def mapRange(value, inMin, inMax, outMin, outMax):
    return outMin + (((value - inMin) / (inMax - inMin)) * (outMax - outMin))


class Controller(object):
    def __init__(self):

        self.ball_buildings = ["2", "6", "5"]
        self.laser_buildings = ["1", "4", "3"]

        self.heater_buildings = ["7", "8", "9"]

        # create an MQTT client
        self.mqtt_client = mqtt_client.MQTTClient("mqtt", 1883)
        self.mqtt_client.register_callback("+/events/#", self.handle_events)

        # create a match
        self.match = match.MatchModel(
            self.ball_buildings, self.laser_buildings, self.heater_buildings
        )

    def handle_events(self, topic: str, msg: dict):
        parts = topic.split("/")
        source = parts[0]
        subsystem = parts[2]
        # see if the source is a building
        if source in (
            self.ball_buildings + self.laser_buildings + self.heater_buildings
        ):
            if subsystem in ["laser_detector", "ball_detector"]:
                event_type = msg.get("event_type", None)
                if event_type == "hit":
                    self.match.douse_fire(source)
        elif source == "ui":
            event_type = msg.get("event_type", None)
            if event_type is not None:
                if event_type == "ui_toggle":
                    # logger.debug("got a toggle event")
                    self.match.handle_ui_toggles(msg.get("data"))
                else:
                    logger.debug("Got a normal event")
                    self.match.dispatch(event_type)

    def publish_score(self):
        # publish score
        current_score = self.match.calculate_score()
        self.mqtt_client.publish("ui/state/score", {"current_score": current_score})

    def publish_building_table(self):
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

            row_data["fire_level"] = mapRange(
                building.current_fire_level, 0, 16, 0, 100
            )
            row_data["score"] = building.get_score()
            table_data.append(row_data)

        self.mqtt_client.publish("ui/state/table_data", table_data)

    def publish_toggles(self):
        for key, value in self.match.ui_toggles.items():
            self.mqtt_client.publish(
                f"ui/state/{key}",
                {"data": value}
            )

    def publish_game_state(self):
        # publish the states
        state = self.match.sm.state.name  # type: ignore
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
        self.mqtt_client.publish("ui/state/match_state", {"state": state})

    def publish_timers(self):
        # publish time remainings
        time_left = time.strftime(
            "%M:%S", time.gmtime(self.match.phase_timer.time_remaining)
        )
        self.mqtt_client.publish("ui/state/phase_remaining", {"time": time_left})

        time_left = time.strftime(
            "%M:%S", time.gmtime(self.match.match_timer.time_remaining)
        )
        self.mqtt_client.publish("ui/state/match_remaining", {"time": time_left})

        time_left = 0
        for building_name, building in self.match.heater_buildings.items():
            if building.sm.state.name == "on_fire_state":
                time_left = building.heater_timer.time_remaining

        self.mqtt_client.publish("ui/state/heater_countdown", {"time": time_left})

    def publish_hotspot_building(self):
        # publish the hot spot building
        self.mqtt_client.publish(
            "ui/state/hotspot_building",
            {"building": self.match.random_hotspot_building},
        )

    def publish_safezone(self):
        # publish the hot spot building
        self.mqtt_client.publish(
            "ui/state/safezone",
            {"zone": self.match.safezone},
        )

    def generate_LED_dict(self, building):
        strip_len = 30
        data = {}
        data["pixel_data"] = []
        for i in range(0, strip_len):
            data["pixel_data"].append([0, 0, 0])

        fire_level = building.current_fire_level
        init = building.initial_fire_level
        pixels_per_fs = 2 if init <= 8 else 1

        if fire_level > (init // 2):
            left = (init // 2) * pixels_per_fs
            right = (fire_level - (init // 2)) * pixels_per_fs
        elif fire_level <= (init // 2):
            left = fire_level * pixels_per_fs
            right = 0
        else:
            left = 0
            right = 0

        # do the first window's portion of the led strip
        if left > 0:
            for i in range(0, left):
                data["pixel_data"][i] = [0, 0, 255]
        # do the second window's portion of the led strip
        if right > 0:
            for i in range(strip_len - 1, strip_len - 1 - right, -1):
                data["pixel_data"][i] = [0, 0, 255]

        return data

    def publish_building_LED_commands(self):
        for building_name, building in self.match.fire_buildings.items():

            data = self.generate_LED_dict(building=building)
            self.mqtt_client.publish(f"{building_name}/progress_bar/set", data)

            # handle window portion
            if building.current_fire_level > (building.initial_fire_level / 2):
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window1", "state": "on"}
                )
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window2", "state": "on"}
                )
            elif building.current_fire_level > 0:
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window1", "state": "on"}
                )
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window2", "state": "off"}
                )
            else:
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window1", "state": "off"}
                )
                self.mqtt_client.publish(
                    f"{building_name}/relay/set", {"channel": "window2", "state": "off"}
                )

            # handle the hopper portion
            relay_channel = "hopper"

            state = "on" if self.match.sm.state.name == "phase_3_state" else "off"
            self.mqtt_client.publish(
                f"{building_name}/relay/set", {"channel": relay_channel, "state": state}
            )

    def publish_building_heater_commands(self):
        relay_channel = "heater"
        for building_name, building in self.match.heater_buildings.items():
            state = "off"
            if building.sm.state.name == "on_fire_state":
                state = "on"
            self.mqtt_client.publish(
                f"{building_name}/relay/set", {"channel": relay_channel, "state": state}
            )

    def run(self):
        self.mqtt_client.start_threaded()
        last_update_time = time.time()
        while True:
            if time.time() - last_update_time > .5:
                # publish UI data
                self.publish_score()
                self.publish_game_state()
                self.publish_hotspot_building()
                self.publish_safezone()
                self.publish_timers()
                self.publish_building_table()
                # publish building commands
                self.publish_building_LED_commands()
                self.publish_building_heater_commands()
                last_update_time = time.time()
            self.publish_toggles()
            time.sleep(0.1)


if __name__ == "__main__":
    controller = Controller()
    controller.run()

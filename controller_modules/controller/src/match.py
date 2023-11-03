from pysm import State, StateMachine, Event
import buildings
from threading import Thread, Lock
from typing import Dict, List, Union, Any
import time
import timer
from loguru import logger
import random
import json
import re
import copy


class MatchModel(object):
    def __init__(self, ball_buildings: List[str], laser_buildings: List[str], heater_buildings: List[str]):

        self.score = 0

        self.fire_buildings:Dict[str,buildings.FireBuildingModel] = {}
        for building in ball_buildings:
            self.fire_buildings[building] = buildings.FireBuildingModel(building, initial_fire_level=16, points_per_window=4, b_type="ball")
        for building in laser_buildings:
            self.fire_buildings[building] = buildings.FireBuildingModel(building, initial_fire_level=8, points_per_window=3, b_type="laser")

        self.heater_buildings: Dict[str, buildings.HeaterBuildingModel] = {}
        for building in heater_buildings:
            self.heater_buildings[building] = buildings.HeaterBuildingModel(building)

        with open('/configs/config.json', 'r') as file:
            self.config = json.load(file)

        self.phase_i_duration = self.config.get("phase_1_duration", 10)
        self.phase_ii_duration = self.config.get("phase_2_duration", 10)
        self.phase_iii_duration = self.config.get("phase_3_duration", 120)

        self.random_hotspot_building = None
        self.safezone = None

        self.phase_timer = timer.Timer()
        self.match_timer = timer.Timer()

        self.phase_three_job_should_exit = False

        self.ui_toggles = {
            "sphero_recon": 0,
            "sphero_recon_autonomous": 0,

            "rvr_recon": False,
            "rvr_recon_autonomous": False,

            "tello_recon": False,
            "smoke_jumper_launch": False,
            "smoke_jumper_parachute": False,
            "smoke_jumper_landed_on_touch": False,
            "smoke_jumper_landed_in": False,
            "tello_recon_autonomous": False,

            "avr_takeoff_recon": False,
            "avr_apriltag": False,
            "avr_landing": False,
            "avr_autonomous": False,

            "first_responders_loaded": 0,
            "avr_ided_hotspot_and_dropped_fr": False,
            "avr_flashed_led": False,

            "first_responders_unloaded": 0,
            "stranded_launched_from_fire_escape": 0,
            "stranded_in_rvr" : 0,
            "avr_delivered_first_responders": 0,

            "stranded_delivered_to_safe_zone": 0,
            "tello_identified_safe_zone": False,

            "rvr_handsfree_unloaded": False,

            "avr_water_drop_autonomous": False,

            "rvr_parked": False,
            "first_responders_parked": False,
            "tello_parked": False,
            "avr_parked": False,
            "match_id": ""
        }

        ###############################################################################

        ################### S T A T E  -  M A C H I N E   S T U F F ###################
        self.sm_lock = Lock()
        self.sm: StateMachine = StateMachine('match')

        self.idle_state = State('idle_state')
        self.idle_state.handlers = {
            "enter":self.idle_enter,
            "reset_match_event":self.idle_enter
        }
        self.staging_state = State('staging_state')
        self.staging_state.handlers = {
            "randomize_hotspot_event": self.randomize_building,
            "randomize_safezone_event": self.randomize_safezone,
            "start_preheat_event": self.start_preheat,
        }
        self.phase_1_state = State('phase_1_state')
        self.phase_1_state.handlers = {
            "enter":self.phase_one_enter
        }
        self.phase_2_state = State('phase_2_state')
        self.phase_2_state.handlers = {
            "enter":self.phase_two_enter
        }
        self.phase_3_state = State('phase_3_state')
        self.phase_3_state.handlers = {
            "enter":self.phase_three_enter,
            "exit":self.phase_three_exit,
            "fire_doused_event":self.douse_fire_handler
        }
        self.post_match_state = State('post_match_state')
        self.post_match_state.handlers = {
            "enter": self.post_match_enter,
            "exit": self.post_match_exit
        }

        self.sm.add_state(self.idle_state, initial=True)
        self.sm.add_state(self.staging_state)
        self.sm.add_state(self.phase_1_state)
        self.sm.add_state(self.phase_2_state)
        self.sm.add_state(self.phase_3_state)
        self.sm.add_state(self.post_match_state)

        self.sm.add_transition(self.idle_state, self.staging_state, events=['new_match_event'])
        self.sm.add_transition(self.staging_state, self.phase_1_state, events=['match_start_event'])
        self.sm.add_transition(self.phase_1_state, self.phase_2_state, events=['phase_i_timeout_event'])
        self.sm.add_transition(self.phase_2_state, self.phase_3_state, events=['phase_ii_timeout_event'])
        self.sm.add_transition(self.phase_3_state, self.post_match_state, events=['phase_iii_timeout_event'])

        self.sm.add_transition(self.phase_1_state, self.post_match_state, events=['match_end_event'])
        self.sm.add_transition(self.phase_2_state, self.post_match_state, events=['match_end_event'])
        self.sm.add_transition(self.phase_3_state, self.post_match_state, events=['match_end_event'])


        self.sm.add_transition(self.staging_state, self.idle_state, events=['reset_match_event'])
        self.sm.add_transition(self.post_match_state, self.idle_state, events=['reset_match_event'])

        self.sm.initialize()

    def dispatch(self, event):
        self.sm_lock.acquire()

        prev_state = self.sm.state.name #type: ignore
        if isinstance(event, str):
            event = Event(event)
        self.sm.dispatch(event)
        new_state = self.sm.state.name #type: ignore

        if new_state != prev_state:
            logger.debug(f"MATCH: State changed to {new_state}")

        self.sm_lock.release()

    def idle_enter(self, state, enter):
        self.random_hotspot_building = ""
        self.safezone = ""
        for building in self.fire_buildings.values():
            building.auto_ignite = False
            building.reset()
        for building in self.heater_buildings.values():
            building.reset()
        self.reset_ui_toggles()

    def phase_one_enter(self, state, event):
        logger.debug("starting phase 1 timer thread!")

        self.phase_timer.function = self.phase_i_timeout
        self.phase_timer.set_timeout(self.phase_i_duration)
        self.phase_timer.start()

        self.match_timer.function = None
        self.match_timer.set_timeout(self.phase_i_duration + self.phase_ii_duration + self.phase_iii_duration)
        self.match_timer.start()

    def phase_two_enter(self, state, event):
        logger.debug("starting phase 2 timer!")
        self.phase_timer.function = self.phase_ii_timeout
        self.phase_timer.set_timeout(self.phase_ii_duration)
        self.phase_timer.start()

    def phase_three_enter(self, state, event):
        logger.debug("starting phase 3 timer!")
        self.phase_timer.function = self.phase_iii_timeout
        self.phase_timer.set_timeout(self.phase_iii_duration)
        self.phase_timer.start()

        self.phase_three_job_thread = Thread(target=self.phase_three_job, args=())
        self.phase_three_job_thread.start()

        for building in self.fire_buildings.values():
            building.ignite()
            # building.auto_ignite = True

    def phase_three_exit(self, state, event):
        self.phase_three_job_should_exit = True
        self.phase_three_job_thread.join()
        self.phase_three_job_should_exit = False

    def phase_three_job(self):
        while True:
            if self.phase_three_job_should_exit:
                break
            # if any building's state isn't extinguished
            if any([building.sm.state.name != "extinguished_state" for building in self.fire_buildings.values()]):
                #we're still waiting for the buildings to be extinguished
                pass
            # otherwise if they've all been extinguished
            else:
                #ignite them all
                time.sleep(5)
                for building in self.fire_buildings.values():
                    building.ignite()
            time.sleep(.1)

    def douse_fire_handler(self, state, event: Event):
        building = event.cargo["source"]
        if building in self.fire_buildings.keys():
            self.fire_buildings[building].douse_fire()

    def post_match_enter(self, state, event):
        self.match_timer.reset()
        self.phase_timer.reset()

    def post_match_exit(self, state, event):
        match_id = self.ui_toggles["match_id"]
        if match_id != "" and self.calculate_score() > 0:

                score_json = copy.deepcopy(self.ui_toggles)
                score_json["buildings"] = {}
                for id, building in self.fire_buildings.items():
                    score_json["buildings"][str(id)] = {}
                    score_json["buildings"][str(id)]["hits"] = building.get_hits()
                    score_json["buildings"][str(id)]["windows"] = building.get_windows()

                score_json["safezone"] = str(self.safezone)
                score_json["hotspot"] = str(self.random_hotspot_building)

                filename = match_id
                filename = filename.replace("-", "_")
                filename = "".join([c for c in filename if re.match(r'\w', c)])
                with open(f"/logs/{filename}.json","w") as file:
                    file.write(json.dumps(score_json, indent=2))


    def randomize_building(self, state, event):
        self.randomize_hotspot()

    def randomize_safezone(self, state, event):
        self.random_zone()

    def phase_i_timeout(self):
         self.dispatch(Event("phase_i_timeout_event"))

    def phase_ii_timeout(self):
         self.dispatch(Event("phase_ii_timeout_event"))

    def  phase_iii_timeout(self):
         self.dispatch(Event("phase_iii_timeout_event"))

    def start_preheat(self, state, event):
        if self.random_hotspot_building is not None and self.random_hotspot_building != "":
            self.heater_buildings[self.random_hotspot_building].ignite()

    ########################################################
    def calculate_phase_i(self):
        score = 0

        #phase I
        if self.ui_toggles["sphero_recon_autonomous"] > 0:
            score += self.ui_toggles["sphero_recon_autonomous"] * 2
        if self.ui_toggles["sphero_recon"] > 0:
            score += self.ui_toggles["sphero_recon"]


        if self.ui_toggles["rvr_recon_autonomous"] is True:
            score += 5
        else:
            if self.ui_toggles["rvr_recon"] is True:
                score += 2

        if self.ui_toggles["tello_recon_autonomous"] is True:
            score += 4
        elif self.ui_toggles["tello_recon"] is True:
            score +=2

        if self.ui_toggles["tello_recon_autonomous"] is True:
            if self.ui_toggles["smoke_jumper_launch"]:
                score += 3
            if self.ui_toggles["smoke_jumper_parachute"]:
                score += 2
            if self.ui_toggles["smoke_jumper_landed_in"]:
                score += 5
            elif self.ui_toggles["smoke_jumper_landed_on_touch"]:
                score += 3
        else:
            if self.ui_toggles["smoke_jumper_launch"]:
                score += 1
            if self.ui_toggles["smoke_jumper_parachute"]:
                score += 1
            if self.ui_toggles["smoke_jumper_landed_in"]:
                score += 3
            elif self.ui_toggles["smoke_jumper_landed_on_touch"]:
                score += 1

        if self.ui_toggles["avr_autonomous"] is True:
            if self.ui_toggles["avr_takeoff_recon"] is True:
                score += 10
            if self.ui_toggles["avr_apriltag"] is True:
                score += 3
            if self.ui_toggles["avr_landing"] is True:
                score += 7
        else:
            if self.ui_toggles["avr_takeoff_recon"] is True:
                score += 2
            if self.ui_toggles["avr_apriltag"] is True:
                score += 2
            if self.ui_toggles["avr_landing"] is True:
                score += 1

        return score

    def calculate_phase_ii(self):
        score = 0
         #phase 2 vars
        if self.ui_toggles["first_responders_loaded"] > 0:
            score += self.ui_toggles["first_responders_loaded"]

        if self.ui_toggles["avr_ided_hotspot_and_dropped_fr"] is True:
            score += 5
        if self.ui_toggles["avr_flashed_led"] is True:
            score += 5

        if self.ui_toggles["first_responders_unloaded"] > 0:
            score += self.ui_toggles["first_responders_unloaded"]
        if self.ui_toggles["stranded_launched_from_fire_escape"] > 0:
            score += self.ui_toggles["stranded_launched_from_fire_escape"]
        if self.ui_toggles["stranded_in_rvr"] > 0:
            score += self.ui_toggles["stranded_in_rvr"] * 2
        if self.ui_toggles["avr_delivered_first_responders"] > 0:
            score += self.ui_toggles["avr_delivered_first_responders"] * 2

        if self.ui_toggles["stranded_delivered_to_safe_zone"] > 0:
            score += self.ui_toggles["stranded_delivered_to_safe_zone"]
        if self.ui_toggles["tello_identified_safe_zone"] is True:
            score += self.ui_toggles["stranded_delivered_to_safe_zone"]


        if self.ui_toggles["rvr_handsfree_unloaded"] is True:
            score += 5
        return score

    def calculate_phase_iii(self):
        score = 0
        for building in self.fire_buildings.values():
            if building.b_type == "ball":
                score += building.get_score()
                if self.ui_toggles["avr_water_drop_autonomous"]:
                    score += ((building.get_score()/4) * 2)
            elif building.b_type == "laser":
                score += building.get_score()
        if self.ui_toggles["rvr_parked"] is True:
            score += 3
        if self.ui_toggles["first_responders_parked"] > 0:
            score += self.ui_toggles["first_responders_parked"]
        if self.ui_toggles["tello_parked"] is True:
            score += 3
        if self.ui_toggles["avr_parked"] is True:
            score += 3
        return score

    def calculate_score(self):
        #phase I
        phase_i = self.calculate_phase_i()

        #phase 2 vars
        phase_ii = self.calculate_phase_ii()

        #phase 3 vars
        phase_iii = self.calculate_phase_iii()

        cumulative = phase_i + phase_ii + phase_iii

        return cumulative

    def randomize_hotspot(self):
        name, object = random.choice(list(self.heater_buildings.items()))
        self.random_hotspot_building = name

    def random_zone(self):
        zone = random.choice(["RED", "BLUE"])
        self.safezone = zone


    def douse_fire(self, source):
        self.dispatch(Event("fire_doused_event", source=source))

    def reset_ui_toggles(self):
            self.ui_toggles["sphero_recon"] = 0
            self.ui_toggles["sphero_recon_autonomous"] = 0
            self.ui_toggles["rvr_recon"] = False
            self.ui_toggles["rvr_recon_autonomous"] = False
            self.ui_toggles["tello_recon"] = False
            self.ui_toggles["smoke_jumper_launch"] = False
            self.ui_toggles["smoke_jumper_parachute"] = False
            self.ui_toggles["smoke_jumper_landed_on_touch"] = False
            self.ui_toggles["smoke_jumper_landed_in"] = False
            self.ui_toggles["tello_recon_autonomous"] = False
            self.ui_toggles["avr_takeoff_recon"] = False
            self.ui_toggles["avr_apriltag"] = False
            self.ui_toggles["avr_landing"] = False
            self.ui_toggles["avr_autonomous"] = False
            self.ui_toggles["first_responders_loaded"] = 0
            self.ui_toggles["avr_ided_hotspot_and_dropped_fr"] = False
            self.ui_toggles["avr_flashed_led"] = False
            self.ui_toggles["first_responders_unloaded"] = 0
            self.ui_toggles["stranded_launched_from_fire_escape"] = 0
            self.ui_toggles["stranded_in_rvr"] = 0
            self.ui_toggles["avr_delivered_first_responders"] = 0
            self.ui_toggles["stranded_delivered_to_safe_zone"] = 0
            self.ui_toggles["tello_identified_safe_zone"] = False
            self.ui_toggles["rvr_handsfree_unloaded"] = False
            self.ui_toggles["avr_water_drop_autonomous"] = False
            self.ui_toggles["rvr_parked"] = False
            self.ui_toggles["first_responders_parked"] = False
            self.ui_toggles["tello_parked"] = False
            self.ui_toggles["avr_parked"] = False
            self.ui_toggles["match_id"] = ""
    
    def handle_ui_toggles(self, data):
        toggle = data.get("toggle", None)
        payload = data.get("payload", None)
        if toggle in self.ui_toggles.keys():

            #handle the special case
            if toggle=="sphero_recon":
                if self.ui_toggles["sphero_recon_autonomous"] + payload > 3:
                    self.ui_toggles["sphero_recon_autonomous"] = 3 - payload
                    self.ui_toggles["sphero_recon"] = payload
                elif payload <= 3:
                    self.ui_toggles["sphero_recon"] = payload
            elif toggle == "sphero_recon_autonomous":
                if self.ui_toggles["sphero_recon"] + payload > 3:
                    self.ui_toggles["sphero_recon"] = 3 - payload
                    self.ui_toggles["sphero_recon_autonomous"] = payload
                elif payload <= 3:
                    self.ui_toggles["sphero_recon_autonomous"] = payload
            elif toggle == "match_id":
                self.ui_toggles[toggle] = payload
            elif isinstance(payload, bool) or isinstance(payload, int):
                self.ui_toggles[toggle] = payload
        else:
            logger.debug(f"{toggle} not in toggles dict")
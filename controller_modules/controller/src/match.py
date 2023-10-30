from pysm import State, StateMachine, Event
import buildings
from threading import Thread, Lock
from typing import Dict, List, Union, Any
import time
import timer
from loguru import logger
import random
import json


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

        self.phase_timer = timer.Timer()
        self.match_timer = timer.Timer()

        self.phase_three_job_should_exit = False


        #phase I vars

        self.sphero_recon = 0
        self.sphero_recon_autonomous = 0

        self.rvr_recon = False
        self.rvr_recon_autonomous = False
        self.rvr_auto_turns = 0
        self.rvr_enter_fire_station = False

        self.tello_recon = False
        self.tello_recon_autonomous = False

        self.smoke_jumper_launch = False
        self.smoke_jumper_parachute = False
        self.smoke_jumper_landed_on_touch = False
        self.smoke_jumper_landed_in = False
        self.smoke_jumper_autonomous = False

        self.avr_takeoff_recon = False
        self.avr_apriltag = False
        self.avr_landing = False
        self.avr_autonomous = False

        #phase 2 vars
        self.first_responders_loaded = 0
        self.avr_lands_residential = False
        self.avr_residential_autonomous = False
        self.spheros_unloaded = 0
        self.stranded_launch_from_fire_escape = 0
        self.stranded_in_rvr = 0
        self.avr_delivered_first_responders = 0
        self.tello_identified_safe_zone = False #TODO ask rohn
        self.rvr_handsfree_unloaded = False

        #phase 3 vars
        self.avr_water_drop_autonomous = False
        self.rvr_parked = False
        self.first_responders_parked = False
        self.tello_parked = False
        self.avr_parked = False

        ###############################################################################

        phase_i_auto_achieved = False
        phase_ii_auto_achieved = False
        # TODO - get more

        ################### S T A T E  -  M A C H I N E   S T U F F ###################
        self.sm_lock = Lock()
        self.sm: StateMachine = StateMachine('match')

        self.idle_state = State('idle_state')
        self.idle_state.handlers = {
            "enter":self.idle_enter
        }
        self.staging_state = State('staging_state')
        self.staging_state.handlers = {
            "randomize_hotspot_event": self.randomize_building,
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
            "enter": self.post_match_enter
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
        for building in self.fire_buildings.values():
            building.auto_ignite = False
            building.reset()
        for building in self.heater_buildings.values():
            building.reset()
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

    def randomize_building(self, state, event):
        self.randomize_hotspot()

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
    def calculate_score(self):
        score = 0

        if self.sphero_recon_autonomous > 0:
            score += self.sphero_recon_autonomous * 2
        if self.sphero_recon > 0:
            score += self.sphero_recon * 2


        if self.rvr_recon_autonomous is True:
            if self.rvr_auto_turns > 0:
                score += self.rvr_auto_turns
            if self.rvr_enter_fire_station is True:
                score +=2
        else:
            if self.rvr_recon is True:
                score += 2

        if self.tello_recon_autonomous is True:
            score += 4
        elif self.tello_recon is True:
            score +=2

        if self.smoke_jumper_autonomous is True:
            if self.smoke_jumper_launch:
                score += 3
            if self.smoke_jumper_parachute:
                score += 2
            if self.smoke_jumper_landed_on_touch:
                score += 3
            if self.smoke_jumper_landed_in:
                score += 5
        else:
            if self.smoke_jumper_launch:
                score += 1
            if self.smoke_jumper_parachute:
                score += 1
            if self.smoke_jumper_landed_on_touch:
                score += 1
            if self.smoke_jumper_landed_in:
                score += 3

        if self.avr_autonomous is True:
            if self.avr_takeoff_recon is True:
                score += 10
            if self.avr_apriltag is True:
                score += 3
            if self.avr_landing is True:
                score += 7
        else:
            if self.avr_takeoff_recon is True:
                score += 2
            if self.avr_apriltag is True:
                score += 2
            if self.avr_landing is True:
                score += 1

        #phase 2 vars
        if self.first_responders_loaded > 0:
            score += 1
        if self.avr_lands_residential is True:
            score += 5
        if self.avr_residential_autonomous is True:
            score += 5
        if self.spheros_unloaded > 0:
            score += self.spheros_unloaded
        if self.stranded_launch_from_fire_escape > 0:
            score += self.stranded_launch_from_fire_escape
        if self.stranded_in_rvr > 0:
            score += self.stranded_in_rvr * 2
        if self.avr_delivered_first_responders > 0:
            score += self.avr_delivered_first_responders * 2
        # self.tello_identified_safe_zone = False #TODO ask rohn
        if self.rvr_handsfree_unloaded is True:
            score += 5

        #phase 3 vars
        for building in self.fire_buildings.values():
            if building.b_type == "ball":
                score += building.get_score()
                if self.avr_water_drop_autonomous:
                    score += ((building.get_score()/4) * 2)
            elif building.b_type == "laser":
                score += building.get_score()
        if self.rvr_parked is True:
            score += 3
        if self.first_responders_parked > 0:
            score += self.first_responders_parked
        if self.tello_parked is True:
            score += 3
        if self.avr_parked is True:
            score += 3
        return score

    def randomize_hotspot(self):
        name, object = random.choice(list(self.heater_buildings.items()))
        self.random_hotspot_building = name

    def douse_fire(self, source):
        self.dispatch(Event("fire_doused_event", source=source))

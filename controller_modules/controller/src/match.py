from pysm import State, StateMachine, Event
import buildings
from threading import Thread, Lock
from typing import Dict, List, Union, Any
import time
import timer
from loguru import logger
import random


class MatchModel(object):
    def __init__(self, ball_buildings: List[str], laser_buildings: List[str], heater_buildings: List[str]):

        self.score = 0

        self.fire_buildings:Dict[str,buildings.FireBuildingModel] = {}
        for building in ball_buildings:
            self.fire_buildings[building] = buildings.FireBuildingModel(building, initial_fire_level=16, points_per_window=4)
        for building in laser_buildings:
            self.fire_buildings[building] = buildings.FireBuildingModel(building, initial_fire_level=8, points_per_window=3)

        self.heater_buildings: Dict[str, buildings.HeaterBuildingModel] = {}
        for building in heater_buildings:
            self.heater_buildings[building] = buildings.HeaterBuildingModel(building)


        self.phase_i_duration = 10
        self.phase_ii_duration = 10
        self.phase_iii_duration = 120

        self.random_hotspot_building = None

        self.phase_timer = timer.Timer()
        self.match_timer = timer.Timer()

        self.phase_three_job_should_exit = False

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
        for building in self.fire_buildings.values():
            score = score + building.get_score()
        # TODO - do the other stuff here
        return score

    def randomize_hotspot(self):
        name, object = random.choice(list(self.heater_buildings.items()))
        self.random_hotspot_building = name

    def douse_fire(self, source):
        self.dispatch(Event("fire_doused_event", source=source))

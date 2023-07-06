from pysm import State, StateMachine, Event
import buildings
from threading import Thread, Lock
from typing import Dict, List, Union, Any
import time
from loguru import logger
import random

class Timer(object):
    def __init__(self):
        self.time_remaining = 0
        self.enabled = False
        self.function: Any = None
        thread = Thread(target=self.run, args=tuple())
        thread.start()

    def start(self):
        self.enabled = True
    def pause(self):
        self.enabled = False
    def reset(self):
        self.enabled = False
        self.time_remaining = 0
    def set_timeout(self, time):
        self.enabled = False
        self.time_remaining = time

    def run(self):
        while True:
            if self.enabled:
                if self.time_remaining >= 1:
                    self.time_remaining -=1
                if self.time_remaining == 0:
                    if self.function is not None:
                        self.enabled = False
                        self.function()
            time.sleep(1)


class MatchModel(object):
    def __init__(self, fire_buildings: List[str], heater_buildings: List[str]):

        self.score = 0
        self.fire_buildings:Dict[str,buildings.FireBuildingModel] = {}
        for building in fire_buildings:
            self.fire_buildings[building] = buildings.FireBuildingModel(building)

        self.heater_buildings: Dict[str, buildings.HeaterBuildingModel] = {}
        for building in heater_buildings:
            self.heater_buildings[building] = buildings.HeaterBuildingModel(building)


        self.phase_i_duration = 10
        self.phase_ii_duration = 10
        self.phase_iii_duration = 90

        self.random_hotspot_building = None

        self.phase_timer = Timer()
        self.match_timer = Timer()

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
            "randomize_hotspot_event": self.randomize_building
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
            "exit":self.phase_three_exit
        }
        self.post_match_state = State('post_match_state')

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

    def timer(self, timeout, event):
        time.sleep(timeout)
        #logger.debug("dispatching timeout event")
        self.dispatch(Event(event))

    # def phase_timer(self, timeout, event, setter):
    #     start_time = time.time()
    #     elapsed = 0
    #     while elapsed < timeout:
    #         time.sleep(.1)
    #         elapsed = time.time() - start_time
    #         setter(timeout - elapsed)
    #     #logger.debug("dispatching timeout event")
    #     setter(0)
    #     self.dispatch(Event(event))

    def idle_enter(self, state, enter):
        self.random_hotspot_building = ""
        for building in self.fire_buildings.values():
            building.auto_ignite = False
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
        for building in self.fire_buildings.values():
            building.ignite()
            building.auto_ignite = True

    def phase_three_exit(self, state, event):
        self.match_timer.reset()

    def randomize_building(self, state, event):
        self.randomize_hotspot()

    def phase_i_timeout(self):
         self.dispatch(Event("phase_i_timeout_event"))

    def phase_ii_timeout(self):
         self.dispatch(Event("phase_ii_timeout_event"))

    def phase_iii_timeout(self):
         self.dispatch(Event("phase_iii_timeout_event"))

    ########################################################
    def calculate_score(self):
        score = 0
        for building in self.fire_buildings.values():
            score = score + building.score
        # TODO - do the other stuff here
        return score

    def randomize_hotspot(self):
        name, object = random.choice(list(self.heater_buildings.items()))
        self.random_hotspot_building = name

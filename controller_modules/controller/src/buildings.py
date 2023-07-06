from pysm import State, StateMachine, Event
from loguru import logger
from threading import Lock, Thread
import time

class FireBuildingModel(object):
    def __init__(self, name: str, initial_fire_level=16):
        self.name = name
        self.fire_douse_amount = 1
        self.initial_fire_level = initial_fire_level
        self.current_fire_level = 0
        self.auto_ignite = False
        self.score = 0

        #################### S T A T E  M A C H I N E   S T U F F ####################
        self.sm_lock = Lock()

        self.sm = StateMachine('building')

        self.idle_state = State('idle_state')
        self.idle_state.handlers = {
            "enter": self.idle_enter
        }
        self.on_fire_state = State('on_fire_state')
        self.on_fire_state.handlers = {
            "fire_doused_event": self.fire_doused_action,
            "enter":self.on_fire_enter
        }

        self.extinguished_state = State('extinguished_state')
        self.extinguished_state.handlers = {
            "enter": self.extinguished_enter
        }

        self.sm.add_state(self.idle_state, initial=True)
        self.sm.add_state(self.on_fire_state)
        self.sm.add_state(self.extinguished_state)

        self.sm.add_transition(self.idle_state, self.on_fire_state, events=['ignition_event'])
        self.sm.add_transition(self.extinguished_state, self.on_fire_state, events=['ignition_event'])

        self.sm.add_transition(self.on_fire_state, self.idle_state, events=['reset_event'])
        self.sm.add_transition(self.extinguished_state, self.idle_state, events=['reset_event'])

        self.sm.add_transition(self.on_fire_state, self.extinguished_state,events=['fire_extinguished_event'])

        self.sm.initialize()

    def dispatch(self, event):
        self.sm_lock.acquire()
        prev_state = self.sm.state.name #type: ignore
        if isinstance(event, str):
            event = Event(event)
        self.sm.dispatch(event)
        new_state = self.sm.state.name #type: ignore

        if new_state != prev_state:
            logger.debug(f"BUILDING {self.name}: State changed to {new_state} from {prev_state} on {event.name}")
        self.sm_lock.release()

    def idle_enter(self, state, event):
        self.score = 0
        self.current_fire_level = 0

    def on_fire_enter(self, state, event):
        self.current_fire_level = self.initial_fire_level
        # logger.debug(f"BUILDING {self.name}: Catching fire!!!!")

    def timer(self, timeout, event):
        time.sleep(timeout)
        #logger.debug("dispatching timeout event")
        self.dispatch(Event(event))

    def extinguished_enter(self, state, event):
        if self.auto_ignite:
            thread = Thread(target=self.timer, args=(1, "ignition_event"))
            thread.start()

    def fire_doused_action(self, state, event):
        if self.sm.state == self.on_fire_state and self.current_fire_level >= self.fire_douse_amount:
            self.current_fire_level -= self.fire_douse_amount
            self.score += self.fire_douse_amount
            logger.debug(f"BUILDING {self.name}: dousing fire! New score: {self.score} New fire level: {self.current_fire_level}")
            if self.current_fire_level <= 0:
                self.sm.dispatch(Event("fire_extinguished_event"))

    ##############################################################################

    def douse_fire(self):
        logger.debug("Got a doused event, dispatching now")

        self.dispatch(Event('fire_doused_event'))

    def ignite(self):
        self.dispatch(Event('ignition_event'))

    def reset(self):
        self.dispatch(Event('reset_event'))

    def get_fire_level(self):
        return self.current_fire_level

class HeaterBuildingModel(object):
    def __init__(self, name: str):
        self.name = name

        #################### S T A T E  M A C H I N E   S T U F F ####################
        self.sm = StateMachine('heater_building')

        self.idle_state = State('idle_state')
        self.on_fire_state = State('on_fire_state')

        self.sm.add_state(self.idle_state, initial=True)
        self.sm.add_state(self.on_fire_state)

        self.sm.add_transition(self.idle_state, self.on_fire_state, events=['ignition_event'])
        self.sm.add_transition(self.on_fire_state, self.idle_state, events=['reset_event'])
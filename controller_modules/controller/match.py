from pysm import State, StateMachine, Event
from building import Building
from threading import Thread, Lock
import time

class Match(object):
    def __init__(self):

        self.score = 0

        buildings = {
            "A" : Building("A"),
            "B" : Building("B"),
            "C" : Building("C"),
            "D" : Building("D"),
            "E" : Building("E"),
            "F" : Building("F"),
        }
        #################### S T A T E  -  M A C H I N E   S T U F F ####################
        self.sm_lock = Lock()
        self.sm = StateMachine('match')

        self.idle_state = State('idle_state')
        self.staging_state = State('staging_state')
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
            "enter":self.phase_three_enter
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
        self.sm.add_transition(self.phase_1_state, self.phase_2_state, events=['phase_1_timeout_event'])
        self.sm.add_transition(self.phase_2_state, self.phase_3_state, events=['phase_2_timeout_event'])
        self.sm.add_transition(self.phase_3_state, self.post_match_state, events=['phase_3_timeout_event'])
        self.sm.add_transition(self.post_match_state, self.idle_state, events=['match_reset_event'])

        self.sm.initialize()

    def dispatch(self, event):
        self.sm_lock.acquire()
        self.sm.dispatch(event)
        self.sm_lock.release()

    def timer(self, timeout, event):
        time.sleep(timeout)
        self.sm.dispatch(Event(event))

    def phase_one_enter(self, state, event):
        print("starting phase 1 timer!")
        thread = Thread(target=self.timer, args=(90, "phase_1_timeout_event"))
        thread.start()
    def phase_two_enter(self, state, event):
        print("starting phase 2 timer!")
        thread = Thread(target=self.timer, args=(90, "phase_2_timeout_event"))
        thread.start()
    def phase_three_enter(self, state, event):
        print("starting phase 3 timer!")
        thread = Thread(target=self.timer, args=(90, "phase_3_timeout_event"))
        thread.start()

        while True:
            pass
            #process the building events?


if __name__ == "__main__":
    match = Match()
    match.sm.dispatch(Event("new_match_event"))
    match.dispatch(Event("match_start_event"))
    while True:
        time.sleep(1)
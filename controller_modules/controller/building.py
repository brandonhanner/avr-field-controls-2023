from pysm import State, StateMachine, Event

class Building(object):
    def __init__(self, name: str, initial_fire_level=16):
        self.name = name
        self.fire_douse_amount = 1
        self.initial_fire_level = initial_fire_level
        self.current_fire_level = initial_fire_level

        #################### S T A T E  M A C H I N E   S T U F F ####################
        self.sm = StateMachine('building')

        self.idle_state = State('idle_state')
        self.on_fire_state = State('on_fire_state')
        self.on_fire_state.handlers = {
            "fire_doused_event": self.fire_doused_action,
            "enter":self.on_fire_enter
        }

        self.extinguished_state = State('extinguished_state')

        self.sm.add_state(self.idle_state, initial=True)
        self.sm.add_state(self.on_fire_state)
        self.sm.add_state(self.extinguished_state)

        self.sm.add_transition(self.idle_state, self.on_fire_state, events=['ignition_event'])
        self.sm.add_transition(self.extinguished_state, self.on_fire_state, events=['ignition_event'])

        self.sm.add_transition(self.on_fire_state, self.idle_state, events=['reset_event'])
        self.sm.add_transition(self.extinguished_state, self.idle_state, events=['reset_event'])

        self.sm.add_transition(self.on_fire_state, self.extinguished_state,events=['fire_doused_event'], condition=self.extinguished_check)

        self.sm.initialize()

    def on_fire_enter(self, state, event):
        self.current_fire_level = self.initial_fire_level

    def fire_doused_action(self, state, event):
        if self.sm.state == self.on_fire_state:
            self.current_fire_level -= self.fire_douse_amount

    def extinguished_check(self, state, event):
        if self.current_fire_level <= 0:
            return True
        else:
            return False
    ##############################################################################

    def douse_fire(self):
        # print("Got a doused event, dispatching now")

        # print(f"prev_state: {self.sm.state.name}") #type: ignore
        # print(f"prev fire level: {self.current_fire_level}")

        self.sm.dispatch(Event('fire_doused_event'))

        # print(f"new_state: {self.sm.state.name}") #type: ignore
        # print(f"new fire level: {self.current_fire_level}")

    def ignite(self):
        self.sm.dispatch(Event('ignition_event'))

    def reset(self):
        self.sm.dispatch(Event('reset_event'))



if __name__ == "__main__":
    building = Building("RBO")

    print(f"initial state: {building.sm.state.name}") #type: ignore

    building.ignite()

    for i in range(0,16):
        building.douse_fire()

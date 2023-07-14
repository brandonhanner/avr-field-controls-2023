from threading import Thread
from typing import Any
import time

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
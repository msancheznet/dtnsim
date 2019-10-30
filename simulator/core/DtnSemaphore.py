# -*- coding: utf-8 -*-

from simulator.core.DtnCore import Simulable

class DtnSemaphore(Simulable):
    """ Semaphore for a simpy simulation

        The semaphore controller can turn the semaphore green/red by simply doing
        ``semaphore.turn_green()`` or ``semaphore.turn_red()``

        Users that want to cross the semaphore have to first see if it is green by
        doing: ``if semaphore.is_red: yield semaphore.green``

        Users can only wait until the semaphore turns red by doing
        ``if semaphore.is_green: yield semaphore.red``

        .. Warning:: User **must** always check the state of the semaphore before yielding to green.
                     If you yield an event that has already that has already succeed, it will crash
    """
    def __init__(self, env, green=False):
        super().__init__(env)

        # Initialize variables
        self.green = env.event()
        self.red   = env.event()

        # Set the initial state. Do not use the turn_red/green() functions
        # because you do not want to check if things are processed at this point
        if green: self.green.succeed()
        else:     self.red.succeed()

    def turn_green(self):
        # Prevent turning green if already green
        if self.green.triggered: return

        # Indicate not green state
        self.red = self.env.event()

        # Succeed the green event
        self.green.succeed()

    def turn_red(self):
        # Prevent turning red if already red
        if self.red.triggered: return

        # Indicate red state
        self.red.succeed()

        # Create a new event to stop everyone
        self.green = self.env.event()

    @property
    def is_green(self):
        return self.green.triggered

    @property
    def is_red(self):
        return self.red.triggered

class DtnSemaphoreOld(Simulable):
    """ Semaphore for a simpy simulation

        The semaphore controller can turn the semaphore green/red by simply doing
        ``semaphore.turn_green()`` or ``semaphore.turn_red()``

        Users that want to cross the semaphore have to first see if the semaphore
        is green. For that they can do ``if semaphore.red: yield semaphore.green``

        .. Warning:: User **must** always check if the semaphore is red before yielding to green.
                     In other words, the ``if semaphore.red:`` part is mandatory, if you ``yield``
                     and the semaphore is green, it will crash
    """
    def __init__(self, env, green=False):
        super().__init__(env)

        # Flag that is true if the semaphore is red
        self.red = True

        # Event used to stop everyone at the semaphore
        self.green = env.event()

        # If the semaphore should be green, note it
        if green: self.turn_green()

    def turn_green(self):
        # Indicate not green state
        self.red = False

        # Succeed the green event
        self.green.succeed()

    def turn_red(self):
        # Indicate red state
        self.red = True

        # Create a new event to stop everyone
        self.green = self.env.event()

    @property
    def is_green(self):
        return not self.red

    @property
    def is_red(self):
        return self.red



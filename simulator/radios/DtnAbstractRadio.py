import abc
from simulator.core.DtnCore import Simulable

class DtnAbstractRadio(Simulable, metaclass=abc.ABCMeta):
    """ An abstract radio to transmit messages through a connection """

    def __init__(self, env, parent, shared=True):
        # Call parent constructor
        super(DtnAbstractRadio, self).__init__(env)

        # Store variables
        self.parent = parent    # Parent node

        # Counter of energy consumed transmitting
        self.energy = 0.0

    def reset(self):
        pass

    def initialize(self, *args, **kwargs):
        """ Initialize the radio """
        # Find all connections for this node
        self.outcons = {d: self.env.connections[o, d] for o, d in
                           self.env.connections if o == self.parent.nid}

        # Run the radio process
        self.env.process(self.run())

        # Mark as running
        self.running = True

    @property
    def is_alive(self):
        return self.parent.is_alive

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        pass

    def put(self, *args, **kwargs):
        """ Put a message in the radio to transmit. This is a
            non-blocking call
        """
        self.env.process(self.do_put(*args, **kwargs))

    @abc.abstractmethod
    def do_put(self, *args, **kwargs):
        pass
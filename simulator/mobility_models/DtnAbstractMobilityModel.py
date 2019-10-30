import abc
from simulator.core.DtnCore import Simulable

class DtnAbstractMobilityModel(Simulable, metaclass=abc.ABCMeta):
    """ An abstract mobility model """

    def __init__(self, env, props):
        # Call parent constructor
        super(DtnAbstractMobilityModel, self).__init__(env)

        # Store properties
        self.props = props

    @abc.abstractmethod
    def initialize(self, *args, **kwargs):
        pass

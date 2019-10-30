import abc
from collections import defaultdict
import numpy as np

class Simulable(object):
    """ Base class for all simulable objects. It stores the simulation
        environment, registers this class, and provides utility methods
        such as accessing the simulation time, epoch, and configuration.
        It also provides the ``disp`` that displays a message if the
        logger is not active, or logs it otherwise.
    """
    def __init__(self, env):
        # Set simulation environment and logger
        self.env    = env
        self.log    = env.do_log

        # If the environment has a logger, use it
        self.logger = hasattr(env, 'logger')

    @property
    def t(self):
        """ Return current simulation time """
        return self.env.now

    @t.setter
    def t(self, value):
        """ Block settings this property's """
        raise RuntimeError('Cannot set the "t" parameter. It contains the simulation time')

    @property
    def is_alive(self):
        return True if self.env.until is None else (self.t <= self.env.until)

    @is_alive.setter
    def is_alive(self, value):
        """ Block settings this property's """
        raise RuntimeError('Cannot set the "is_alive" parameter.')

    @property
    def epoch(self):
        """ Return current simulation epoch """
        return self.env.epoch

    @epoch.setter
    def epoch(self, value):
        """ Block settings this property's """
        raise RuntimeError('Cannot set the "epoch" parameter. It contains the simulation epoch')

    @property
    def config(self):
        """ Return the configuration structure """
        return self.env.config

    @config.setter
    def config(self, value):
        """ Block settings this property's """
        raise RuntimeError('Cannot set the "config" parameter. It contains the structure'
                           'of global settings for the simulation.')

    def disp(self, msg, *args):
        """ Display a message in the log or sys.out """
        # If not logging is needed, return
        if self.log == False: return

        # If the logger is available in the environment, use it
        if self.logger: self.env.log(msg, *args); return

        # Format logging message
        header = 't={:.3f}:\t'.format(self.env.now)
        msg    = msg.format(*args)

        # Log by simply printing
        print(header + msg.format(*args))

    def __str__(self):
        return '<{}>'.format(self.__class__.__name__)

    def __repr__(self):
        return self.__str__()

class Message(object, metaclass=abc.ABCMeta):
    def __init__(self):
        # Total propagation delay suffered by this Message
        # during transmission
        self.prop_delay = 0.0

        # True/False
        self.has_errors = False

    @property
    @abc.abstractmethod
    def mid(self):
        pass

    @property
    @abc.abstractmethod
    def num_bits(self):
        pass

    def __str__(self):
        return '<Message>'

    def __repr__(self):
        return self.__str__()

class TimeCounter(dict):
    """ Essentially equivalent to ``defaultdict(int)``. Re-implemented to provide
        extra functionality
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self[0] = 0

    def inc(self, t):
        if t in self: self[t] += 1
        else: self[t] = 1

    def dec(self, t):
        if t in self: self[t] -= 1
        else: self[t] = -1

    def to_timeseries(self):
        t = np.array(list(self.keys()))
        v = np.cumsum(list(self.values()))
        return t, v

class LoadMonitor(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Last arrival time logged
        self.last_t = 0.0

        # Second to last arrival logged
        self.prior_to_last = 0.0

    def log(self, t, bundle):
        # If t equals 0, then skip, you can't measure the rate yet
        if t < 0.0: return

        # If t < last_t, error
        if t < self.last_t: raise RuntimeError('t is < than last_t')

        # If t is greater than last arrival
        if t > self.last_t:
            self[t] = bundle.data_vol/(t-self.last_t)
            self.prior_to_last = self.last_t
            self.last_t = t
            return

        # If t == last_t, then just add the bps to the last measurement
        self[t] += bundle.data_vol/(t-self.prior_to_last)

    def to_timeseries(self):
        t = np.array(list(self.keys()))
        v = np.array(list(self.values()))
        return t, v
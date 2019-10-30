import abc
from simulator.ducts.DtnAbstractDuctLTP import DtnAbstractDuctLTP
from simulator.utils.DtnUtils import load_class_dynamically

class DtnAbstractDuctMBLTP(DtnAbstractDuctLTP, metaclass=abc.ABCMeta):
    """ An abstract Multiband LTP duct. It is subclassed by both ``DtnOuductMBLTP`` and
        ``DtnInductMBLTP``. It extends the capabilities of ``DtnAbstractDuctLTP`` by allowing:

        1) Multiple LTP engines that have independent LTP configuration parameters
        2) Mutliple radios, one per band, with its associated queues, data rates and BERs

        The generation of unique session ids for a multiband LTP duct is different from an LTP duct.
        For the latter, you use a hash based function (see ``DtnAbstractDuctLTP``). However, for the
        multiband case you need the session ids to be sequential and therefore we use a counter object.

        The need to have sequential session ids comes from the fact that a segment can arrive at an
        induct for a session that has already succeeded and is no longer available. Therefore, we use
        this sequential property to detect this corner case and not re-open a session for a block that
        has already been delivered to the DTN node.
    """
    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnAbstractDuctMBLTP, self).__init__(env, name, parent, neighbor)

        # For a multi-band LTP, you will have more than one radio. Therefore, index
        # them in a dictionary
        self.radio = {}

        # Counter for session ids
        self.sid_counter = 0

    def initialize(self, peer, *args, bands=None, **kwargs):
        # Call DtnAbstractDuct initializer. Note that you are
        # calling the constructor of the grandparent.
        super(DtnAbstractDuctLTP, self).initialize(peer, **kwargs)

        # Store the bands available in this duct
        self.bands = bands

        # Get the radios to use
        self.radio = {b: self.parent.radios[kwargs[b]] for b in bands}

    def get_session_id(self, block):
        """ Utilize a global session counter. This is needed because session ids
            must be sequential
        """
        self.sid_counter += 1
        return self.sid_counter

    def total_datarate(self, dest):
        return sum(r.datarate for r in self.radio.values())

    @property
    def radios(self):
        return self.radio



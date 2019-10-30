from .DtnAbstractConnection import DtnAbstractConnection, TransmissionError
import numpy as np
from simulator.utils.basic_utils import Counter
from simulator.utils.math_utils import find_consecutive

class DtnDistanceConnection(DtnAbstractConnection):

    def __init__(self, env, cid, orig, dest, props):
        """ Initialize a DtnStaticConnection

            :param DtnSimEnvironment env: Simulation environment
            :param str cid: Connection id as specified in the YAML file (not in the contact plan)
            :param str orig: Id of origin node
            :param str dest: Id of destination node
            :param dict props: Properties of this connection type
        """
        # Call parent constructor
        super(DtnDistanceConnection, self).__init__(env, cid, orig, dest, props)

        # Initialize connection properties
        self.max_dist = props.max_distance

        # Counter for contact ids
        self.cid_counter = Counter()

        # Current contact id as specified in the contact plan
        self.contact_id = None

    def initialize_contacts_and_ranges(self):
        # Call parent function
        super(DtnDistanceConnection, self).initialize_contacts_and_ranges()

        # Get distances for this connection
        self.times = self.mobility_model.times
        try:
            self.dist = self.mobility_model.dist[self.orig.nid, self.dest.nid]
        except KeyError:
            self.dist = self.mobility_model.dist[self.dest.nid, self.orig.nid]

        # Find intervals of time during which this connection is open
        # ints is now a list of lists: [[ts0, te0], [ts1, te1], ...]
        ints = find_consecutive(self.dist <= self.max_dist, val=True)

        # Dictionary of contacts indexed by cid: {cid: (start time, end time, avg propagation delay)
        self.contacts = {next(self.cid_counter): (self.times[ts], self.times[te],
                                                  np.mean(self.dist[ts:te])/3e8)
                                                  for ts, te in ints}

    def run(self):
        # If the no contacts, exit
        if not any(self.contacts): yield self.env.exit()

        # Iterate over contacts
        for cid, (ts, te, tprop) in self.contacts.items():
            # Wait until the start of the contact
            yield self.env.timeout(ts-self.t)

            # Open the connection
            self.open_connection(cid, tprop, te-ts, te)

            # Wait until the contact ends
            yield self.env.timeout(self.duration)

            # Close the connection
            self.close_connection()

    def set_contact_properties(self, cid, prop, dur, te):
        ''' Set properties of the current contact '''
        self.contact_id = cid
        self.prop_delay = prop
        self.duration   = dur
        self.next_close = te

    def reset_contact_properties(self):
        ''' Reset the properties of ending contact '''
        self.contact_id = None
        self.prop_delay = None
        self.duration   = None
        self.next_close = None

    def transmission_error(self, message):
        err = '\n****** Cannot send message while connection is closed ******\n'
        err += f't={self.t}:\tPropagation delay for connection ({self.orig}, {self.dest}) is None\n'
        err += '\n' + repr(message) + '\n'
        err += 'Range interval table:\n'
        err += str(self.contacts)
        raise TransmissionError(err)
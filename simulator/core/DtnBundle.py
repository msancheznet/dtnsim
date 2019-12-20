from copy import deepcopy
from simulator.core.DtnCore import Message


critical_priority = 0
bulk_priority     = 0

class Bundle(Message):
    # Counter for the bundle id
    bid_counter   = 0

    # Counter for the bundle copy id {bid: cid, bid: cid, ...}
    copy_counters = {}

    # Counter for the flow id
    fid_counter   = 0

    # Variables to export into a dictionary. See ``to_dict``
    export_vars   = ['fid', 'bid', 'cid', 'orig', 'dest', 'data_vol', 'data_type', 'critical', 'visited',
                     'arrived', 'dropped', 'arrival_time', 'creation_time', 'latency', 'allowable_lat',
                     'prop_delay', 'drop_reason', 'priority']

    def __init__(self, env, orig, dest, data_type, data_vol, latency, critical,
                 fid=None, eid=0, TTL=float('inf'), priority=bulk_priority):
        # Call parent constructor
        super(Bundle, self).__init__()

        # Set the bundle ids
        self.set_bundle_ids(fid)

        # Set bundle properties
        self.orig          = orig
        self.dest          = dest
        self.eid           = eid            # By default 0. This is a generic EID
        self.data_type     = data_type
        self.data_vol      = data_vol       # [bits]
        self.allowable_lat = latency        # [seconds]
        self.critical      = critical
        self.TTL           = TTL
        self.priority      = critical_priority if critical else priority

        # Initialize other properties
        self.visited  = []
        self.excluded = []
        self.arrived  = False
        self.dropped  = False
        self.arrival_time  = None
        self.creation_time = env.now
        self.latency       = None
        self.prop_delay    = 0
        self.drop_reason   = ''                 # Only filled if ``dropped = True``

        # Dictionary of extension blocks
        self.eblocks = {}

    @classmethod
    def from_flow(cls, env, flow):
        # Create new bundle
        bundle = Bundle(env, flow['Orig'], flow['Dest'], flow['DataType'],
                        flow['BundleSize'], flow['Critical'], flow['Latency'],
                        fid=flow['fid'])

        # If the flow defines a route, store it too
        if 'Route' in flow: bundle.route = flow['Route']

        return bundle

    def set_bundle_ids(self, fid=None):
        # Create bundle unique ID
        self.__class__.bid_counter += 1
        self.bid = self.__class__.bid_counter

        # Create a bundle copy ID
        self.__class__.copy_counters[self.bid] = 0
        self.cid = 0

        # If the flow id is provided, just use it
        if fid: self.fid = fid; return

        # Otherwise, create a new one
        self.__class__.fid_counter += 1
        self.fid = self.__class__.bid_counter

    def __hash__(self):
        """ To compute the hash of a bundle, hash a tuple consisting on the bundle id and the copy id
            (recall that multiple copies of a bundle are possible if it is critical)
        """
        return hash((self.bid, self.cid))

    @property
    def mid(self):
        return (self.bid, self.cid)

    @property
    def num_bits(self):
        return self.data_vol

    def copy(self, t):
        new_bundle = deepcopy(self)
        new_bundle.creation_time = t
        return new_bundle

    def __deepcopy__(self, memo):
        # Create new bundle object
        cls        = self.__class__
        new_bundle = cls.__new__(cls)
        memo[id(self)] = new_bundle

        # Deepcopy all attributes
        for k, v in self.__dict__.items():
            setattr(new_bundle, k, deepcopy(v, memo))

        # Increase the copy counter
        self.__class__.copy_counters[self.bid] += 1
        new_bundle.cid = self.__class__.copy_counters[self.bid]

        return new_bundle

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__class__.export_vars}

    def __repr__(self):
        return 'Bundle {}'.format(self.mid)

    def __str__(self):
        return str(self.to_dict())
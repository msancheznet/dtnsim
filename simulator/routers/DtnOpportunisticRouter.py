import numpy as np
from .DtnAbstractRouter import DtnAbstractRouter, RtRecord

class DtnOpportunisticRouter(DtnAbstractRouter):

    def __init__(self, env, parent):
        super().__init__(env, parent)

        # Flag this as an opportunistic router
        self.opportunistic = True

    def initialize(self, *args, **kwargs):
        pass

    def find_routes(self, bundle, first_time, *kwargs):
        # Increase counter
        self.counter += 1

        # Figure out the priority of this bundle (0=critical, 1=false)
        priority = self.find_bundle_priority(bundle)

        # Get a new record
        rec = self.new_record(bundle, priority)

        # Return a record
        return [rec], []

    def new_record(self, bundle, priority):
        # Initialize variables
        con = {'cid': None, 'orig': self.parent.nid, 'dest': None, 'tstart': 0.0, 'tend': np.inf,
               'duration': np.inf, 'capacity': np.inf, 'range': np.nan, 'rate': np.nan}
        rte = {'tstart': 0.0, 'tend': np.inf, 'contacts': ()}

        # If you reach this point, create a routing record and use it
        return RtRecord(bundle=bundle, contact=con, route=rte, priority=priority, neighbor='opportunistic')
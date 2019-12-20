from simulator.routers.DtnAbstractRouter import DtnAbstractRouter, RtRecord

import numpy as np

class DtnSourceRouter(DtnAbstractRouter):
    def initialize(self, *args, **kwargs):
        pass

    def find_routes(self, bundle, first_time, **kwargs):
        # Find the current node in the route
        try:
            idx = bundle.route.index(self.parent.nid)
        except ValueError:
            return [], []

        # If this is the end of the route, error. The bundle should not
        # be routed in the first place
        if idx == len(bundle.route)-1:
            raise RuntimeError('This bundle should not be routed.')

        # Figure out the priority of this bundle (0=critical, 1=false)
        priority = self.find_bundle_priority(bundle)

        # Initialize dummy variables
        con = {'cid': None, 'orig': self.parent.nid, 'dest': bundle.route[idx+1],
               'tstart': 0.0, 'tend': np.inf, 'duration': np.inf,
               'capacity': np.inf, 'range': np.nan, 'rate': np.nan}
        rte = {'tstart': 0.0, 'tend': np.inf, 'contacts': ()}

        # Create a dummy routing record
        rec = RtRecord(bundle=bundle, contact=con, route=rte, priority=priority, neighbor=con['dest'])

        # Return a record
        return [rec], []
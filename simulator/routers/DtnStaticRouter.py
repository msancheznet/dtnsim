from .DtnAbstractRouter import DtnAbstractRouter, RtRecord
import numpy as np

class DtnStaticRouter(DtnAbstractRouter):
    def initialize(self):
        # Get the static routes
        self.next_hop = self.props.routes

        # Down-select the routes for this node
        self.next_hop = self.next_hop[self.parent.nid] if self.parent.nid \
                        in self.next_hop else None

    def find_routes(self, bundle, first_time, **kwargs):
        # If this node does not have any routes assigned to it, throw error
        # TODO: This should be checked in a parser
        if not self.next_hop:
            raise RuntimeError(f'Node {self.parent.nid} does not have any '
                               f'routes specified and uses a static router')

        # Increase counter
        self.counter += 1

        # Figure out the priority of this bundle (0=critical, 1=false)
        priority = self.find_bundle_priority(bundle)

        # Initialize variables
        con = {'cid': None, 'orig': self.parent.nid, 'dest': None, 'tstart': 0.0, 'tend': np.inf,
               'duration': np.inf, 'capacity': np.inf, 'range': np.nan, 'rate': np.nan}
        rte = {'tstart': 0.0, 'tend': np.inf, 'contacts': ()}

        # If there is a route indicated, use it
        if bundle.dest in self.next_hop: con['dest'] = self.next_hop[bundle.dest]

        # If there is a default next hop, use it
        if 'default' in self.next_hop: con['dest'] = self.next_hop['default']

        # If the next hop could not be computed, return empty. At the DtnNode, this will
        # force the bundle to be dropped since you do not know how to route it. Therefore,
        # the limbo is not used in this case.
        if not con['dest']: return [], []

        # If you reach this point, create a routing record and use it
        rec = RtRecord(bundle=bundle, contact=con, route=rte, priority=priority, neighbor=con['dest'])

        # Return a record
        return [rec], []

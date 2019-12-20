import abc
from collections import namedtuple
from simulator.core.DtnCore import Simulable

""" A routing record to be returned by a router when a bundle needs to be
    routed in the network. It contains the following information:
    
    1) bundle: The bundle that this record applies to
    2) neighbor: ID of the duct through which to send (see ``DtnNode.store_routed_bundle``)
    3) contact: Next contact in the route as a dictionary
        ``{'cid': Contact id in the contact plan. If not known (e.g. static routing), use None 
           'orig': 'N1',
           'dest': 'N2',        
           'tstart': 0.0,
           'tend': 63072000.0,
           'duration': 63072000,
           'capacity': 79218432000000.0,
           'range': 600,
           'rate': 1256000.0}``
    4) route: End to end route that has been computed for this bundle along
              with information on the route validity
              - Example 1 (from CGR):    ``{'contacts': (1,), 'tend': 63072000, 'tstart': 0}``
              - Example 2 (from static): ``{'contacts': (),   'tend': np.inf,   'tstart': 0}``
    5) priority: 0 if critical, 1 if standard
"""
class RtRecord():
    def __init__(self, bundle=None, contact=None, route=None,
                 priority=None, neighbor=None):
        self.bundle   = bundle
        self.contact  = contact
        self.route    = route
        self.priority = priority
        self.neighbor = neighbor

    def to_dict(self):
        if self.bundle is None:
            return {}

        d = self.bundle.to_dict()
        d['neighbor'] = self.neighbor
        d.update(self.contact)

        return d

class DtnAbstractRouter(Simulable, metaclass=abc.ABCMeta):
    """ An abstract router """
    def __init__(self, env, parent):
        # Call parent constructor
        super(DtnAbstractRouter, self).__init__(env)

        # Initialize variables
        self.parent = parent
        self.type   = self.config[parent.type].router
        self.props  = self.config[self.type]

        # Counter for number of times the routing procedure is called
        self.counter = 0

        # If this router is opportunistic in nature, flag it
        # By default, assume false
        self.opportunistic = False

    def reset(self):
        pass

    @abc.abstractmethod
    def initialize(self, *args, **kwargs):
        pass

    @property
    def is_alive(self):
        return self.parent.is_alive

    @abc.abstractmethod
    def find_routes(self, bundle, first_time, **kwargs):
        """ This function is called by the DtnNode to route a bundle

            :param bundle: Bundle to route
            :param first_time: True if this is the first time this is routed
            :param kwargs: Arguments specific to each router
            :return: Tuple with the following elements (in this order):

                1) List of RtRecords to use when forwarding this bundle. The contact
                   within the RtRecord will be used to infer which neighbor to forward
                   this bundle towards. If none, return empty list ([]).
                2) List of cids (i.e. list of integers) that indicate which contacts
                   should not be used to forward this bundle. They are provided to the
                   node's limbo function that adds them to the bundle excluded node.
                   If none, return empty list ([]).

            .. tip:: If the return value of this function is ([], []), then the bundle
                     will be dropped.
        """
        pass

    def find_bundle_priority(self, bundle):
        ''' 0=critical, 256=bulk '''
        return bundle.priority

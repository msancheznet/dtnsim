# -*- coding: utf-8 -*-

from collections import defaultdict
from copy import deepcopy
import importlib
import pandas as pd
from simulator.core.DtnQueue import DtnQueue
from simulator.core.DtnCore import Simulable
from simulator.utils.DtnUtils import load_class_dynamically
from simulator.endpoints.DtnDefaultEndpoint import DtnDefaultEndpoint
from .DtnCgrNeighborManager import DtnCgrNeighborManager

class DtnNode(Simulable):
    
    def __init__(self, env, nid, props):
        super().__init__(env)
        # Initialize node properties
        self.nid   = nid
        self.type  = env.config['network'].nodes[nid].type
        self.alias = env.config['network'].nodes[nid].alias
        self.props = props
        
        # Initialize variables
        self.generators = {}                 # Map: {generator type: Generator class}
        self.queues     = {}                 # Map: {neighbor id: DtnNeighborManager}
        self.neighbors  = []                 # List of neighbors as specified in config file
        self.radios     = {}                 # Map: {radio id: Radio class}
        self.endpoints  = {}                 # Map: {eid: Endpoint class}

        # Convergence layers. This is a map of map of maps of the following form
        # {neighbor id: duct id: induct/ouduct: DtnAbstractDuct subclass}
        self.ducts = defaultdict(lambda: defaultdict(dict))

        # Queue to store all bundles that are waiting to be forwarded
        self.in_queue = DtnQueue(env)

        # Queue for the limbo
        self.limbo_queue = DtnQueue(env)
        
        # Create variables to store results
        self.dropped = []

    def reset(self):
        # Reset node elements
        self.router.reset()
        self.selector.reset()
        for _, gen in self.generators.items(): gen.reset()
        for _, radio in self.radios.items(): radio.reset()

    @property
    def available_radios(self):
        return self.radios
        
    def initialize(self):
        """ Initialize the node. Note that his can only be done after the connections
            have been created.
        """
        self.mobility_model = self.env.mobility_models[self.props.mobility_model]

        # Initialize bundle generators for this node
        self.initialize_bundle_generators()

        # Initialize the band selector
        self.initialize_outduct_selector()

        # Initialize radios. Note: This must be done prior to initializing
        # the ducts since ducts require radios. Ducts are initialized in the
        # environment.
        self.initialize_radios()

        # Now that you have created everything, start the forward and limbo managers
        self.env.process(self.forward_manager())
        self.env.process(self.limbo_manager())

    def initialize_bundle_generators(self):
        # Initialize variables
        config = self.env.config

        # Get the list of generators for this node
        gens = config[self.type].generators

        # Instantiate generators dynamically based on class name
        for gen in gens:
            clazz  = getattr(config[gen], 'class')
            module = importlib.import_module(f'simulator.generators.{clazz}')
            clazz  = getattr(module, clazz)

            # Create the generator
            self.generators[gen] = clazz(self.env, self, config[gen])

            # Initialize the generator
            self.generators[gen].initialize()

    def initialize_router(self):
        # Initialize variables
        config = self.env.config

        # Get type of router for this node
        router_type = config[self.type].router

        # Instantiate generators dynamically based on class name
        clazz = load_class_dynamically('simulator.routers', getattr(config[router_type], 'class'))
        self.router = clazz(self.env, self)

        # Initialize this router
        self.router.initialize()

        # If this router is not opportunistic, you are done
        if not self.router.opportunistic: return

        # If this is an opportunistic router, then a specialized queue
        # manager is needed.
        clazz = load_class_dynamically('simulator.nodes', config[router_type].manager)
        self.queues['opportunistic'] = clazz(self.env, self, config[router_type])

    def initialize_outduct_selector(self):
        # Initialize variables
        config = self.env.config

        # Get type of router for this node
        selector_type = config[self.type].selector

        # Instantiate generators dynamically based on class name
        clazz  = getattr(config[selector_type], 'class')
        module = importlib.import_module(f'simulator.selectors.{clazz}')
        clazz  = getattr(module, clazz)
        self.selector = clazz(self.env, self)

        # Initialize this router
        self.selector.initialize()

    def initialize_radios(self):
        # Iterate over the radios
        for radio in self.props.radios:
            # Create the radio for this duct
            class_name = getattr(self.config[radio], 'class')
            clazz = load_class_dynamically('simulator.radios', class_name)

            # Get properties
            radio_props = dict(self.config[radio])

            # Store the new radio
            self.radios[radio] = clazz(self.env, self)

            # Initialize the radio
            self.radios[radio].initialize(**radio_props)

    def initialize_neighbors_and_ducts(self):
        # Iterate over all neighbors
        for orig, neighbor in self.env.connections.keys():
            # If this is not the right origin, continue
            if orig != self.nid: continue

            # Store this neighbor
            self.neighbors.append(neighbor)

            # Create and store the priority queue for this neighbor
            self.queues[neighbor] = DtnCgrNeighborManager(self.env, self, neighbor)

            # Get the neighbor node and the connection between them
            other = self.env.nodes[neighbor]
            conn  = self.env.connections[self.nid, neighbor]

            # Iterate over defined ducts and create them
            for duct_id, duct_name in self.env.config[conn.type].ducts.items():
                # Get the properties of this duct
                props = self.env.config[duct_name]

                # Initialize variables
                iduct, oduct = None, None

                # Create the induct and outduct
                for class_name in getattr(props, 'class'):
                    # Load class type. Since you can't know if it is an induct or outduct,
                    # try both.
                    try:
                        clazz = load_class_dynamically('simulator.ducts.inducts', class_name)
                    except ModuleNotFoundError:
                        clazz = load_class_dynamically('simulator.ducts.outducts', class_name)

                    # Construct depending on whether it is an induct or outduct
                    if clazz.duct_type == None:
                        raise RuntimeError(f'{clazz} has no duct_type defined. Is it an induct or outduct?')
                    elif clazz.duct_type == 'outduct':
                        oduct = clazz(self.env, duct_id, self, neighbor)
                    elif clazz.duct_type == 'induct':
                        iduct = clazz(self.env, duct_id, other, orig)
                    else:
                        raise RuntimeError('f{clazz} has duct_type = {clazz.duct_type}. Valid options are "induct" and '
                                           '"outduct"')

                # If either the ouduct or induct are not set, throw error
                if iduct == None or oduct == None:
                    raise RuntimeError('Could not create duct f{duct_id}')

                # Store the newly created ducts
                self.ducts[neighbor][duct_id]['outduct'] = oduct
                other.ducts[orig][duct_id]['induct'] = iduct

            # Iterate over defined ducts and initialize them. This is done separately
            # since you need to have created all ducts to initialize them for ParallelLTP
            for duct_id, duct_name in self.env.config[conn.type].ducts.items():
                # Get the properties of this duct
                props = self.env.config[duct_name]

                oduct = self.ducts[neighbor][duct_id]['outduct']
                iduct = other.ducts[orig][duct_id]['induct']

                # Initialize duct parameters. Initialization must happen after creating the ducts
                # since they must point to each other.
                oduct.initialize(iduct, **dict(props))
                iduct.initialize(oduct, **dict(props))

        # For now, assume that there is no need for an opportunistic queue.
        # If so, it will be initialized with the router.
        self.queues['opportunistic'] = None

    def initialize_endpoints(self):
        # Add any additional endpoints
        for eid, ept_class in self.props.endpoints.items():
            # Handle special case for default endpoint
            if eid == 0:
                self.endpoints[eid] = DtnDefaultEndpoint(self.env, self)
                self.endpoints[eid].initialize()
                continue

            # Find the endpoint type
            clazz = load_class_dynamically('simulator.endpoints', ept_class)

            # Store the new endpoint
            self.endpoints[eid] = clazz(self.env, self)

            # Initialize endpoint
            if eid in self.config:
                self.endpoints[eid].initialize(**dict(self.config[eid]))
            else:
                self.endpoints[eid].initialize()

    def initialize_neighbor_managers(self):
        for neighbor, mgr in self.queues.items():
            if neighbor.lower() == 'opportunistic':
                continue
            mgr.initialize()

    def forward_manager(self):
        """ This agent pulls bundles from the node incoming queue for processing.
            It ensures that this happens one at a time following the order in which
            they are added to the queue. Note that both new bundles and bundles awaiting
            re-routers will be directed to the ``in_queue`` (see ``forward`` vs ``limbo``)
        """
        # Iterate forever looking for new bundles to forward
        while self.is_alive:
            # Wait until there is a bundle to process
            item = yield from self.in_queue.get()

            # Depack item
            bundle, first_time = item[0], item[1]

            # Trigger forwarding mechanism. If you add a delay in the forwarding mechanism,
            # this delay will be preserved here. To have non-blocking behavior, use
            # ``self.env.process(self.process_bundle(item[0], first_time=item[1])``
            self.process_bundle(bundle, first_time=first_time)
        
    def process_bundle(self, bundle, first_time=True):
        """ Process this bundle in the node. This entails:
                1) If this node is the destination, you are done
                2) Otherwise, route the bundle
                3) If no routes are available, drop
                4) Otherwise, put the bundle into one or more neighbor queues to await transmission by
                   the corresponding convergence layer

            :param bundle: The bundle to forward
            :param first_time: True if this is the first time this node sees this bundle
        """
        # If this bundle has errors, drop immediately
        if bundle.has_errors:
            self.drop(bundle, 'error')
            return

        # It this bundle exceeds the TTL, drop
        if self.check_bundle_TTL(bundle):
            return

        # Add this node in the list of visited nodes (NOTE: must be done before ``find_routes``)
        if first_time: bundle.visited.append(self.nid)

        # Reset the list of excluded contacts
        if first_time: bundle.excluded = []

        # If bundle has reached destination, simply store
        if bundle.dest == self.nid: self.arrive(bundle); return

        # Get contacts for this bundle
        records_to_fwd, cids_to_exclude = self.router.find_routes(bundle, first_time)

        # If router asks for limbo, send this bundle there
        if records_to_fwd == 'limbo':
            self.limbo(bundle, cids_to_exclude)
            return

        # If you can neither forward nor re-route, then drop
        if not records_to_fwd and not cids_to_exclude:
            self.drop(bundle, 'unroutable')
            return

        # If the router has indicated to drop, do it
        if records_to_fwd == 'drop':
            self.drop(bundle, 'router_drops')
            return

        for record in records_to_fwd:
            # Log this successful routers event
            self.disp('{} is routed towards {}', record.bundle, record.contact['dest'])

            # Get the record to forward. If critical and first time, deepcopy it
            to_fwd = deepcopy(record) if bundle.critical and first_time else record

            # Pass the bundle to the appropriate neighbor manager
            self.store_routed_bundle(to_fwd)

        # If you have forwarded at least once, you are done
        if records_to_fwd: return

        # Trigger re-routers excluding the appropriate contacts
        self.limbo(bundle, cids_to_exclude)

    def store_routed_bundle(self, rt_record):
        # Get the neighbor node to send to 
        neighbor = rt_record.neighbor

        # Put in the queue
        self.queues[neighbor].put(rt_record, rt_record.priority)
        
    def forward_to_outduct(self, neighbor, rt_record):
        """ Called whenever a bundle successfully exits a DtnNeighborManager """
        # Initialize variables
        bundle = rt_record.bundle

        # Get the outduct for this bundle
        duct = self.selector.select_duct(neighbor, bundle)

        # If bundle TTL is exceeded, do not forward
        if self.check_bundle_TTL(bundle):
            return
        
        # Put bundle in the convergence layer
        duct['outduct'].send(bundle)

    def forward(self, bundle):
        """ Put a bundle in the queue of bundles to route. Forward should be used
            the first time that you route a bundle. For bundles that are being
            re-routed, use ``limbo`` instead

            .. Tip:: This function never blocks despite the ``yield from`` because
                     the input queue has infinite capacity
        """
        self.env.process(self.do_forward(bundle))

    def do_forward(self, bundle):
        yield from self.in_queue.put((bundle, True))

    def limbo(self, bundle, contact_ids):
        """ Put a bundle in the queue of bundles to route (this bundle is re-routed
            and thus this is equivalent to ION's limbo). Add the provided contacts
            as excluded since you already tried to send this bundle through them

            .. Tip:: This function never blocks despite the ``yield from`` because
                     the input queue has infinite capacity
        """
        # HACK: If contact_ids is None, try re-routing again
        if contact_ids is not None:
            if not isinstance(contact_ids, (list, tuple)): contact_ids = (contact_ids,)
            bundle.excluded.extend(contact_ids)
        self.env.process(self.do_limbo(bundle))

    def do_limbo(self, bundle):
        # If you do not have a limbo wait finite, wait for a second here.
        # Otherwise you will try to re-route the bundle at the same instant
        # in time, thus creating an infinite loop
        if self.props.limbo_wait == float('inf'):
            yield self.env.timeout(1)

        # Add to the limbo queue
        yield from self.limbo_queue.put((bundle, False))

    def limbo_manager(self):
        # Initialize variables
        dt = self.props.limbo_wait

        # if dt = inf, then you want to pause the limbo until there
        # is something in it
        check_empty = dt == float('inf')

        while self.is_alive:
            # Wait for a while. Only do this if you specified a rate at
            # which to pull from the queue
            if not check_empty: yield self.env.timeout(dt)

            # Get everything from the queue
            items = yield from self.limbo_queue.get_all(check_empty=check_empty)

            # Put all items in the input queue
            for item in items:
                yield from self.in_queue.put(item)

    def check_bundle_TTL(self, bundle):
        if self.t-bundle.creation_time < bundle.TTL:
            return False

        # Drop the bundle
        self.drop(bundle, f'TTL (t={self.t})')

        return True

    def arrive(self, bundle):
        # If node is not alive, delete
        if not self.is_alive:
            self.drop(bundle, 'dead_node')

        # Mark arrival
        self.disp('{} arrives at destination', bundle)
        bundle.arrived      = True
        bundle.arrival_time = self.t
        bundle.latency      = bundle.arrival_time - bundle.creation_time

        # Dispatch bundle to the appropriate endpoint depending on the bundle EID
        self.endpoints[bundle.eid].put(bundle)
        
    def drop(self, bundle, drop_reason):
        self.disp('{} is dropped at node {}', bundle, self.nid)
        bundle.dropped     = True
        bundle.drop_reason = drop_reason
        self.dropped.append(bundle)

    def radio_error(self, message):
        self.disp('Error in radio')

    def __str__(self):
        return '<DtnNode {}>'.format(self.nid)
            


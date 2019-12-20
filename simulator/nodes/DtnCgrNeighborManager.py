from collections import defaultdict, deque
from copy import deepcopy
import simpy
from simulator.core.DtnCore import Simulable
from simulator.core.DtnLock import DtnLock
from simulator.core.DtnSemaphore import DtnSemaphore
from simulator.nodes.DtnOverbookeableQueue import DtnOverbookeableQueue
from simulator.utils.DtnIO import prepare_contact_plan

class DtnCgrNeighborManager(Simulable):
    """ Implements the following functions:
        
            1) Open/close queue given the contact plan
            2) Transmit overdue mechanism when a bundle exits 
            3) Re-routers of bundles due to overbooking
    """
    def __init__(self, env, parent, neighbor):
        super().__init__(env)

        # Store the node that contains this manager, it is a DtnNode
        self.parent = parent
        
        # Store the neighbor this manager is taking care of. It is a string
        self.neighbor = neighbor
        
        # Create a queue that can be locked
        self.queue = DtnOverbookeableQueue(env, self)

        # Store the next (or current) contact being considered
        self.current_cid = None

        # Store bundles that should be processed in future contacts
        self.future         = defaultdict(deque)
        self.future_backlog = defaultdict(int)

        # Lock to ensure that all operations related to putting one bundle in
        # the queue are "atomic"
        self.put_lock = DtnLock(env)

        # Semaphore for this queue to know if bundles can be sent to the
        # outducts (or the connection is closed)
        self.outduct_sem = DtnSemaphore(env)

    def initialize(self):
        # Store the contact plan for this manager
        self.cp = prepare_contact_plan(self.parent.nid,
                                       self.neighbor,
                                       self.parent.mobility_model.contacts_df)

        # Create the process that monitors the connection's semaphore
        # and start/stops the queue_extractor when it opens/closes
        self.env.process(self.connection_monitor())
        
        # Run the extractor process
        self.env.process(self.queue_extractor())

    @property
    def is_alive(self):
        return self.parent.is_alive

    @property
    def stored(self):
        return self.queue.stored

    @property
    def capacity(self):
        return self.queue.capacity

    def put(self, rt_record, priority, where='left'):
        # Get the contact id for the contact to be used. If this rt_record
        # comes from CGR routing, this will be specified because you have
        # a contact plan. If this rt_record comes from static routing, the
        # cid is None, therefore, override it.
        cid = rt_record.contact['cid']
        if cid is None: cid = self.current_cid

        # If this bundle is not routed through the current contact, store it
        if cid != self.current_cid:
            self.future[cid].appendleft(rt_record)
            self.future_backlog[cid] += rt_record.bundle.data_vol
            return

        # Process the put operation
        self.env.process(self.do_put(rt_record, priority, where))
        
    def do_put(self, rt_record, priority, where):
        # Only one bundle can be put into the queue at a time. Otherwise, you
        # have race conditions (e.g. you make room for a bundle but before you
        # actually get put in queue someone else takes your room)
        yield self.put_lock.acquire()

        # Put the bundle in the queue. The first argument is True/False
        # The second argument tells you which bundles were removed to make room
        # for this one.
        to_reroute = yield from self.queue.put(rt_record, priority, where=where)
        
        # Re-route bundles
        for record in to_reroute:
            self.reroute(record, reason='overbooked')

        # Release the lock to signal that another bundle can start the process
        # of getting added to the queue
        self.put_lock.release()
            
    def send(self, rt_record):
        # Initialize variables
        bundle   = rt_record.bundle
        capacity = self.capacity

        # Compute time at which the bundle will optimistically reach
        # destination. Note that if the radio has a big queue of bundles,
        # then the packet might get lost altogether because by the time
        # the radio gets to it, the contact will have expired. But since DTN
        # cannot tap into the radio's queue state, there is no way to know it.
        Trx = self.t + bundle.data_vol/self.current_dr + self.current_range

        # Transmit Overdue: If the route has ended by the time it is sent, re-route
        if Trx > rt_record.route['tend']:
            self.reroute(rt_record, False)
            return

        # HACK. Capacity should not be None, but if it is, send to reroute
        if capacity is None:
            self.reroute(rt_record, reason='transmit overdue')
            return

        # Fragment the bundle if necessary
        if capacity < bundle.data_vol:
            # Create a copy of this bundle with the data that does not fit
            new_record = deepcopy(rt_record)
            new_record.bundle.data_vol = bundle.data_vol - capacity
            rt_record.bundle.data_vol = capacity

            # Put the part that does not fit back into the queue
            self.queue.put(new_record, rt_record.priority, where='right')
        
        # Send this bundle using the appropriate outduct
        self.parent.forward_to_outduct(self.neighbor, rt_record)
        
    def reroute(self, rt_record, reason):
        # Initialize variables
        bundle = rt_record.bundle

        # Log re-routers event
        self.disp('{} is being re-routed due to {}', bundle, reason)

        # If reason is transmit overdue, then you have more capacity
        if reason == 'transmit overdue' and self.queue.capacity is not None:
            self.queue.capacity += bundle.data_vol

        # Inform the bundle about this re-routing event so that the capacity
        # is added back to future contacts. Not all routers have this feature,
        # so check if it is needed
        if hasattr(self.parent.router, 'route_failed'):
           self.parent.router.route_failed(rt_record)

        # Create list of bundles to exclude
        cids = []
        if self.current_cid is not None: cids.append(self.current_cid)
        if self.current_cid != rt_record.contact['cid']: cids.append(rt_record.contact['cid'])

        # Add bundle to node's limbo
        self.parent.limbo(bundle, cids)

    def connection_monitor(self):
        # If no contact plan available, exit
        if self.cp is None: yield self.env.exit()

        # If contact plan has not valid entries, exit
        if self.cp.empty: yield self.env.exit()

        # Iterate over range intervals
        for cid, row in self.cp.iterrows():
            # Wait until the contact starts
            yield self.env.timeout(max(0.0, row['dtstart']))

            # Set the current contact properties
            self.current_cid      = cid
            self.current_dr       = row['rate']
            self.current_range    = row['range']
            self.queue.capacity   = row['duration']*self.current_dr
            self.queue.next_close = row['tend']
            self.queue.data_rate  = self.current_dr

            # If there are bundles waiting for this contact, process them immediately
            self.vacate_backlog()

            # Turn the outduct semaphore green
            self.outduct_sem.turn_green()

            # Wait until the contact ends
            yield self.env.timeout(row['duration'])

            # Delete current contact properties
            self.current_cid      = None
            self.current_dr       = None
            self.current_range    = None
            self.queue.capacity   = None
            self.queue.next_close = None
            self.queue.data_rate  = None

            # Turn the outduct semaphore red
            self.outduct_sem.turn_red()

    def vacate_backlog(self):
        # Check if there is backlog for this contact
        if self.current_cid not in self.future:
            return

        # Add the backlog to the queue
        while self.future[self.current_cid]:
            rt_record = self.future[self.current_cid].pop()
            self.future_backlog[self.current_cid] -= rt_record.bundle.data_vol
            self.put(rt_record, rt_record.priority)
        
    def queue_extractor(self):
        while self.is_alive:
            # Wait until the outduct is active
            if self.outduct_sem.is_red: yield self.outduct_sem.green

            # Wait until there is something in the queue
            rt_record = yield from self.queue.get()
            
            # Log and monitor exit of bundle
            self.disp('{} departs from the manager', rt_record.bundle)
            
            # Send this bundle towards the convergence layer
            self.send(rt_record)

            # Do throttling mechanism, i.e you cannot send for a while. This "matches" the exit of bundles
            # from the priority queue and the throughput available in the convergence layer.
            yield self.env.timeout(rt_record.bundle.data_vol/self.current_dr)
    
from simulator.core.DtnBundle import Bundle
from simulator.core.DtnCore import Simulable
from simulator.core.DtnLock import DtnLock
from simulator.core.DtnQueue import DtnQueue
from simulator.core.DtnPriorityDict import DtnPriorityDict
from simulator.nodes.DtnOverbookeableQueue import DtnOverbookeableQueue

class DtnEpidemicManager(Simulable):

    def __init__(self, env, parent, params):
        # Call parent constructor
        super().__init__(env)

        # Store the node that contains this manager, it is a DtnNode
        self.parent = parent

        # Create a queue that can be locked and set the capacity to the specified value
        self.queue = DtnMaxCapacityQueue(env, parent, params.max_buffer_size)

        # Handshake queue
        self.handshake_queue = DtnQueue(env)

        # Lock to ensure that all operations related to putting one bundle in
        # the queue are "atomic"
        self.put_lock = DtnLock(env)

        # Get all connections possible for this node
        self.cons = {d: c for (o, d), c in self.env.connections.items() if o == self.parent.nid}

        # Create an engine for each connection in the system
        for dest, con in self.cons.items():
            # Process to get elements out of the queue to transmit
            env.process(self.queue_extractor(dest, con))

    @property
    def is_alive(self):
        return self.parent.is_alive

    def put(self, rt_record, priority):
        self.env.process(self.do_put(rt_record, priority))

    def do_put(self, rt_record, priority):
        # Only one bundle can be put into the queue at a time. Otherwise, you
        # have race conditions (e.g. you make room for a bundle but before you
        # actually get put in queue someone else takes your room)
        yield self.put_lock.acquire()

        # Put the bundle in the queue. Bundles that where used to make ro
        to_drop = yield from self.queue.put(rt_record, priority, where='left')

        # Drop bundles
        for rt_record in to_drop:
            self.parent.drop(rt_record.bundle, drop_reason='Opportunistic queue full')

        # Release the lock to signal that another bundle can start the process
        # of getting added to the queue
        self.put_lock.release()

    def queue_extractor(self, dest, conn):
        while self.is_alive:
            # Wait until the next connection starts
            if conn.is_red: yield conn.green

            # Handshake with other node see which data is missing on other node
            # NOTE: This is a blocking call since you cannot do the rest until
            # this is completed.
            to_send = yield from self.do_handshake(dest, conn)

            # If the connection red again, continue
            if conn.is_red: continue

            # Send all data that was flagged as missing in the other node
            for rt_record in to_send:
                # Log and monitor exit of bundle
                self.disp('{} departs from the manager', rt_record.bundle)

                # Send this bundle towards the convergence layer
                self.send(dest, rt_record)

                # If the connection red again, continue
                if conn.is_red: continue

            # Wait until connection ends
            if conn.is_green: yield conn.red

    def send(self, dest, rt_record):
        self.parent.forward_to_outduct(dest, rt_record)

    def do_handshake(self, dest, conn):
        # Gather list of all bundles you have
        bids = tuple(self.queue.keys())

        # Create a bundle
        bnd = Bundle(self.env, self.parent.nid, dest, 'telemetry', 16+8*len(bids), 1, False, eid=1)

        # Add the data to this bundle
        bnd.data = bids

        # Get a new routing record. 1 = critical priority
        rt_record = self.parent.router.new_record(bnd, 1)

        # Send this record
        self.send(dest, rt_record)

        # Wait until either the connection ends or you receive the response
        # of the handshaking mechanism
        yield conn.red | self.handshake_queue.is_empty()

        # If the connections is red, then the handshake has failed
        if conn.is_red: return

        # Get the bundle from the peer
        bnd = yield from self.handshake_queue.get()

        print('hola')

class DtnMaxCapacityQueue(DtnOverbookeableQueue):
    """ An overbookeable queue with max capacity """
    def __init__(self, env, parent, max_capacity):
        super().__init__(env, parent)

        # Create a priority ordered dict for this manager. It will override the queue created
        # by the parent class. Essentially we are monkeypatching the queue to get the desired
        # functionality.
        self.queue = DtnPriorityDict(env)

        # Create the critical and bulk priority levels
        self.queue.new_priority_level(0)  # Critical
        self.queue.new_priority_level(1)  # Bulk

        # Fix max capacity
        self._max_capacity = max_capacity

    def keys(self):
        return self.queue.keys()

    @property
    def capacity(self):
        return self._capacity

    @capacity.setter
    def capacity(self, value):
        self._capacity = min(value, self._max_capacity)

    def put(self, rt_record, priority, where='left'):
        # Add to queue
        to_drop = yield from super().put(rt_record, priority, where=where)

        # Return bundles to drop
        return to_drop

    def make_room(self, bundle):
        # If the bulk priority queue is empty, there is no extra room
        if not self.queue.items[1]: return ()

        # Get all items in the bulk priority queue
        blk_items = self.queue.items[1]

        # Initialize variables
        room, i, N = 0, 0, len(blk_items)

        # Iterate over bulk items to see how many do you need
        while True:
            # Count room by taking one out (NOTE: An item contains a rt_record)
            room += blk_items[i].data.bundle.data_vol

            # If this is the last bulk bundle, break
            if i == N - 1: break

            # If you already have enough room, break
            if room >= bundle.data_vol: break

            # Increment the number of bundles to pop
            i += 1

        # If not enough room is available, fail.
        if bundle.data_vol > room + self.capacity: return ()

        # Gather the list of bundles to remove (always from the bulk queue)
        # NOTE 1: Popleft always from bulk queue
        # NOTE 2: DO NOT use list comprehension with yields from inside!
        removed = []
        for _ in range(i + 1):
            rt_record = yield from self.queue.popleft(1)
            removed.append(rt_record)

        # Add capacity back to the queue for the room you just made
        self.capacity += sum(record.bundle.data_vol for record in removed)

        # Return list of bulk bundles to be removed
        return removed





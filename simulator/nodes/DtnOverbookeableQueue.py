from simulator.core.DtnLock import DtnLock
from simulator.core.DtnCore import Simulable
from simulator.core.DtnBundle import critical_priority, bulk_priority
from simulator.core.DtnPriorityQueue import DtnPriorityQueue

class DtnLockeablePriorityQueue(Simulable):
    """ Implements the locking mechanism for when a contact is not available """
    def __init__(self, env, parent):
        super().__init__(env)
        self.monitor = self.env.monitor

        # Store the node that contains this manager, it is a node
        self.parent = parent

        # Create a priority queue for this manager
        self.queue = DtnPriorityQueue(env)

        # Create the critical and bulk priority levels
        self.queue.new_priority_level(critical_priority)    # Critical
        self.queue.new_priority_level(bulk_priority)  # Bulk

        # Create a lock. When closed, no elements can be taken from the queue
        self.lock = DtnLock(env)

        # Acquire the key initially, i.e. close the door
        self.close()
        self.disp('Gate is closed')

        # Total number of bits accumulated in the queue
        self.backlog = 0.0

        # If no need to monitor, return
        if self.monitor == False: return

        # Initialize variables for monitoring the gate
        self.open_times    = []
        self.close_times   = []

    @property
    def is_alive(self):
        return self.parent.is_alive

    @property
    def stored(self):
        return self.queue.stored

    @property
    def items(self):
        return self.queue.items

    def put(self, rt_record, priority, where='left'):
        # Log the arrival
        self.disp('{} with priority {} is put into the manager {}-{}',
                  rt_record.bundle, priority, self.parent.parent.nid, self.parent.neighbor)

        # Add this bundle data volume to the backlog
        self.backlog += rt_record.bundle.data_vol

        # Put in the queue
        yield from self.queue.put(rt_record, priority, where=where)

    def get(self):
        # Wait until there is something to take out
        rt_record = yield from self.queue.get()

        # Log the departure
        self.disp('{} is retrieved from the manager', rt_record.bundle)

        # Subtract this bundle data volume from the backlog
        self.backlog -= rt_record.bundle.data_vol

        return rt_record

    def close(self):
        return self.lock.acquire()

    def open(self):
        self.lock.release()

    def monitor_gate_open(self):
        if self.monitor == False: return
        self.open_times.append(self.t)

    def monitor_gate_close(self):
        if self.monitor == False: return
        self.close_times.append(self.t)

class DtnOverbookeableQueue(DtnLockeablePriorityQueue):
    """ Implements the overbooking mechanism """

    def __init__(self, env, parent):
        super().__init__(env, parent)

        # Data rate of the output of this queue
        self.data_rate = None

        # Capacity counter
        self._capacity = 0

        # Time of next closing
        self.next_close = None

    @property
    def capacity(self):
        # If the gate is already closed, just return counter
        if self.next_close == None: return self._capacity

        # The gate is opened, so capacity is equal to min between
        # the capacity that is left from the time the previous bundle
        # arrived, and the capacity left in the current contact
        return min(self._capacity, self.data_rate * (self.next_close - self.t))

    @capacity.setter
    def capacity(self, value):
        self._capacity = value

    def put(self, rt_record, priority, where='left'):
        # Initialize variables
        bundle = rt_record.bundle

        # If there is enough capacity left in this contact, just add the bundle to the queue
        if self.capacity > bundle.data_vol:
            yield from self.put_in_queue(rt_record, priority, where=where)
            return ()

        # If not enough capacity and this bundle is non-critical, then it needs
        # to be re-routed. Return False to indicate that it is not accepted here
        if not bundle.critical: return (rt_record,)

        # Figure out how many non-critical bundles you need to remove to make
        # room for this bundle. If you cannot make room for this bundle, removed = ()
        removed = yield from self.make_room(bundle)

        # If success is indicated, put the bundle in
        if removed:
            yield from self.put_in_queue(rt_record, priority, where=where)
            return removed

        # If you reach this point, you where not able to make room for this bundle.
        # Therefore, trigger re-routing
        return (rt_record,)

    def put_in_queue(self, rt_record, priority, where='left'):
        # Subtract capacity from the contact
        self.capacity -= rt_record.bundle.data_vol

        # If capacity goes to negative, raise error
        if self.capacity < 0:
            raise RuntimeError('Capacity for DtnOverbookeableQueue is < 0')

        # Trigger the put operation
        yield from super().put(rt_record, priority, where=where)

    def make_room(self, bundle):
        # If the bulk priority queue is empty, there is no extra room
        if not self.queue.items[1]: return ()

        # Get all items in the bulk priority queue
        blk_items = self.queue.items[1]

        # Initialize variables
        room, i, N = 0, 0, len(blk_items)

        # Iterate over bulk items to see how many do you need
        while self.is_alive:
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

# -*- coding: utf-8 -*-

from collections import defaultdict, deque
from heapq import heappush
import pandas as pd
import simpy
from simulator.core.DtnCore import LoadMonitor, Simulable, TimeCounter

class DtnPriorityQueue(Simulable):
    """ New FIFO queue with priority (least is more priority) and (if needed) max capacity. To use it:

            1) Create the queue:  ``q = DtnPriorityQueue(env, capacity=10)``
            2) Put a new element: ``yield from q.put(item, priority)`` or ``yield env.process(q.put(item, priority))``
            3) Get an element:    ``yield from q.get(item)`` or ``yield env.process(q.get(item))``

        .. Tip:: Starting in Python 3.3, you can use the ``yield from`` construct. Prior to that,
                 you must use the ``yield env.process(...)`` form

        .. Tip:: The specified capacity is for the sum over all packets regardless of their
                 priority.

        .. Tip:: You can also explicitly way for the non-empty event. This is useful because it
                 allows you to pull an element from the queue if multiple conditions occur. Consider
                 the following code:

        .. code-block:: python
            :linenos:

            # Wait until the queue is not empty or a timeout of 2 seconds expires, whichever
            # happens first
            yield queue.is_empty() | env.timeout(2)

            # If the queue is still empty, you are done
            if not queue: return

            # If queue is not empty, get data
            data = yield from queue.get()

        .. Danger:: When putting/getting an element in the queue, if ``yield from`` is not used, then nothing
                    will happen, even if the capacity for the queue is set to infinity. If that is the case,
                    the ``put`` method will never block, but you still need to ``yield from`` it.
    """
    def __init__(self, env, capacity=float('inf')):
        # Call parent constructor
        super().__init__(env)

        # Store items in deques. They key to the dictionary is the priority level
        self.items = {}

        # List of priority levels (least is better). It always stays sorted by using
        # a heappush operation when a new priority level is registered
        self.priorities = []

        # Monitor for the number of elements in the queue. If no elements are
        # present in the queue, it will stop the get method.
        self.stop = simpy.Container(env, init=0, capacity=capacity)

    def __len__(self):
        """ Returns the total number of elements in this queue across
            all priorities
        """
        return sum(len(q) for q in self.items.values())

    def __bool__(self):
        """ Returns true if at least there is one element in any priority level """
        return any(self.items.values())

    @property
    def stored(self):
        d  = {p: pd.DataFrame([b.to_dict() for b in self.items[p]]) for p in self.priorities}
        df = pd.DataFrame() if not d else pd.concat(d.values())
        return df

    def put(self, item, priority, where='left'):
        # Count the new addition. If there is not enough capacity, this will block
        yield self.stop.put(1)

        # If this priority level is not known, add create new queue
        if priority not in self.items: self.new_priority_level(priority)

        # Add the element to the appropriate queue
        self.add_to_queue(item, priority, where)

    def get(self, where='right', check_empty=True):
        # Wait until there is at least one element in the queue. Only do it if the queue is
        # empty. This allows the calling function to either ``data = yield from queue.get()``
        # or to (1) ``yield queue.is_empty(); data = yield from queue.get()``
        if check_empty: yield self.is_empty()

        # Iterate over the queues in priority order. Recall that self.priorities
        # is always sorted
        for priority in self.priorities:
            # If this priority level is empty, continue
            if not any(self.items[priority]): continue

            # Get the next element in this priority level
            return self.get_from_queue(priority, where=where)

    def new_priority_level(self, priority):
        # Register the new priority level
        heappush(self.priorities, priority)

        # Create a new queue for this priority level
        self.items[priority] = deque()

    def popleft(self, priority, check_empty=True):
        """ Pop from the beginning of the queue.
            NOTE: This pops from the left, ``get`` pops from the right
        """
        # Wait until there is at least one element in the queue
        if check_empty: yield self.is_empty()

        # Return the item in this priority level
        return self.items[priority].popleft()

    def is_empty(self):
        return self.stop.get(1)

    def add_to_queue(self, item, priority, where):
        if   where == 'left':  self.items[priority].appendleft(item)
        elif where == 'right': self.items[priority].append(item)
        else: raise RuntimeError('"where" can only be "left" or "right"')

    def get_from_queue(self, priority, where):
        if where == 'left':  return self.items[priority].popleft()
        if where == 'right': return self.items[priority].pop()
        raise RuntimeError('"where" can only be "left" or "right"')



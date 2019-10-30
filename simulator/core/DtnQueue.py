# -*- coding: utf-8 -*-

from collections import deque
from simulator.core.DtnCore import Simulable, TimeCounter
import pandas as pd
import simpy

class DtnQueue(Simulable):
    """ New FIFO queue and (if needed) max capacity. To use it:
        
        1) Create the queue:  ``q = DtnQueue(env, capacity=10)``
        2) Put a new element: ``yield from q.put(item)`` or ``yield env.process(q.put(item))``
        3) Get an element:    ``yield from q.get(item)`` or ``yield env.process(q.get(item))``
    
        .. Tip:: Starting in Python 3.3, you can use the ``yield from`` construct. Prior to that,
                 you must use the ``yield env.process(...)`` form

        .. Tip:: You can also explicitly wait for the non-empty event. This is useful because it
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
                 
        .. Danger:: When putting an element in the queue, if ``yield from`` is not used, then nothing
                    will happen, even if the capacity for the queue is set to infinity. So, to put an
                    element in the queue you **must** ``yield from`` it. If you have set capacity to
                    infinity, then this operation will never block, but that is the expected behavior
    """
    def __init__(self, env, capacity=float('inf')):
        super().__init__(env)
        
        # Store items in a deque
        self.items = deque()
        
        # Monitor for the number of elements in the queue. If no elements are 
        # present in the queue, it will stop the get method.
        self.stop = simpy.Container(env, init=0, capacity=capacity)

    def __len__(self):
        """ Returns the number of elements in this queue """
        return len(self.items)

    def __bool__(self):
        """ Returns true if there is at least one element in the queue """
        return len(self.items) != 0

    def __getitem__(self, item):
        """ Access an item in the queue """
        return self.items[item]

    def __iter__(self):
        return iter(self.items)

    @property
    def stored(self):
        # Handle empty case
        if len(self.items) == 0:
            return pd.DataFrame()

        # Get data to store
        d = {i: d for i, d in enumerate(self.items)}

        # If the data can be converted to dict, do it
        if hasattr(d[0], 'to_dict'):
            d = {i: d.to_dict() for i, d in enumerate(self.items)}
        else:
            # HACK for radios. Items stored are a tuple. Bundle is in 1st elem
            d = {i: d[1].to_dict() for i, d in enumerate(self.items)}

        return pd.DataFrame.from_dict(d, orient='index')
        
    def put(self, item, where='left'):
        # Count the new addition. If there is not enough capacity, this will block
        yield self.stop.put(1)
        
        # Add an item to the queue
        if where == 'left':    self.items.appendleft(item)
        elif where == 'right': self.items.append(item)
        else: raise RuntimeError('"where" can only be "left" or "right"')

    def get(self, check_empty=True):
        # Wait until there is at least one element in the queue. Only do it if the queue is
        # empty. This allows the calling function to either ``data = yield from queue.get()``
        # or to (1) ``yield queue.is_empty(); data = yield from queue.get()``
        if check_empty: yield self.is_empty()

        # Get the next item
        return self.items.pop()

    def get_all(self, check_empty=True):
        # Wait until there is at least one element in the queue. Only do it if the queue is
        # empty. This allows the calling function to either ``data = yield from queue.get()``
        # or to (1) ``yield queue.is_empty(); data = yield from queue.get()``
        if check_empty: yield self.is_empty()

        # Copy the items of the queue into a new list
        data = list(self.items)

        # Clear all queue contents
        self.items.clear()

        # Return all items
        return data

    def is_empty(self):
        return self.stop.get(1)

    def __str__(self):
        return '<DtnQueue>'

    def __repr__(self):
        return '<DtnQueue at {}>'.format(hex(id(self)))
    
    
    

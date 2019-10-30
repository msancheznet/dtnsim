from collections import OrderedDict
from heapq import heappush
from simulator.core.DtnPriorityQueue import DtnPriorityQueue

class DtnPriorityDict(DtnPriorityQueue):

    def new_priority_level(self, priority):
        # Register the new priority level
        heappush(self.priorities, priority)

        # Create a new queue for this priority level
        self.items[priority] = OrderedDict()

    def keys(self):
        # Initialize variables
        k = set()

        # Grab all keys in all priority levels
        for priority in self.items:
            k.update(tuple(self.items[priority].keys()))

        return k

    def remove(self, mid, priority):
        return self.items[priority].pop(mid)

    def add_to_queue(self, item, priority, where):
        if   where == 'left':  self.items[priority][item.data.mid] = item
        elif where == 'right': raise NotImplementedError
        else: raise RuntimeError('"where" can only be "left" or "right"')

    def get_from_queue(self, priority, where):
        if   where == 'left':  return self.items[priority].popitem(last=True)
        elif where == 'right': return self.items[priority].popitem(last=False)
        else: raise RuntimeError('"where" can only be "left" or "right"')
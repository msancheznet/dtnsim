# -*- coding: utf-8 -*-

from collections import deque
import simpy
from simulator.core.DtnCore import Simulable


class DtnLockException(Exception):
    pass

class DtnLock(Simulable):
    """ This class implements a traditional lock in the Simpy world.
        In this version, there are not priorities.
        
        Usage examples:
            
            1) To create the lock: ``lock = DtnLock(env)``
            2) To acquire the lock and block until it is ready: ``yield lock.acquire()``
            3) To release the lock: ``lock.release()``
    """
    def __init__(self, env):
        super().__init__(env)

        # The lock is modeled as resource of capacity 1
        self.lock = simpy.Resource(env, capacity=1)
        
        # Since the simpy.Resource is FIFO, we can store the
        # key to all the lock requests into a Python FIFO queue.
        self.keys = deque()
        
        # If true, this is lock is taken
        self.taken = False
        
    def acquire(self):
        # Acquire the lock and save it in the key queue
        key = self.lock.request()
        self.keys.appendleft(key)
        return key
        
    def release(self):
        try:
            key = self.keys.pop()
            self.lock.release(key)        
        except IndexError:
            raise DtnLockException()
    
# =============================================================================
# === TESTING Lock
# =============================================================================    

bundle = 0
    
def agent(pid, env, lock, produce_rate=10, consume_rate=50):
    global bundle
    
    while True:
        # Wait for a while
        yield env.timeout(expovariate(1/produce_rate))
        
        # Create a new bundle
        bundle += 1
        
        # Print bundle arrival
        print('t={:.3f}:\tProducer {} wants to transmit bundle {}'.format(env.now, pid, bundle))
        
        # Acquire the lock
        yield lock.acquire()
        
        # Print transmission start
        print('t={:.3f}:\tProducer {} starts transmission of bundle {}'.format(env.now, pid, bundle))
        
        # Wait while transmission occurs
        yield env.timeout(expovariate(1/consume_rate))
        
        # Print transmission end
        print('t={:.3f}:\tProducer {} ends transmission of bundle {}'.format(env.now, pid, bundle))
        
        # Release the lock to let someone else transmit
        lock.release()
    
if __name__ == '__main__':
    # Imports for testing
    from random import expovariate
    
    # Initialize constants
    SIM_TIME = 1000
    
    # Create simulation environment
    env     = simpy.Environment()
    env.log = True
    lock    = DtnLock(env)
    
    # Run simulation environment
    env.process(agent(1, env, lock))
    env.process(agent(2, env, lock))
    env.process(agent(3, env, lock))
    
    # Run simulation
    env.run(until=SIM_TIME)
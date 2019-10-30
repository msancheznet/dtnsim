from random import expovariate, random
from simulator.core.DtnCore import Simulable

class Transmitter(Simulable):
    ''' Basic transmitter for testing. Bundle are just integers to facilitate 
        unique id and counting
    '''
    def __init__(self, env, fun, rate=10, blocking=True):
        super().__init__(env, log=True)
        self.records  = {}
        self.fun      = fun
        self.rate     = rate
        self.blocking = blocking
        
        # Run the producing process
        env.process(self.run())
        
    def run(self):
        bundle = 0
        while True:
            yield self.env.timeout(expovariate(1/self.rate))
            print('t={:3f}:\tTransmitter creates bundle {}'.format(self.env.now, bundle))
            self.records[bundle] = self.t
            
            # If blocking is True, then use yield from
            if self.blocking == True:
                yield self.env.process(self.fun(bundle))
            else:
                self.env.process(self.fun(bundle))
            
            bundle += 1    
            
class PriorityTransmitter(Simulable):
    ''' Basic transmitter for testing. Bundle are just integers to facilitate 
        unique id and counting
    '''
    def __init__(self, env, fun, rate=10, prob_blk=0.5, blocking=True):
        super().__init__(env, log=True)
        self.records  = {}
        self.fun      = fun
        self.rate     = rate
        self.prob_blk = prob_blk
        self.blocking = blocking
        
        # Run the producing process
        env.process(self.run())
        
    def run(self):
        bundle = 0
        while True:
            yield self.env.timeout(expovariate(1/self.rate))
            print('t={:3f}:\tTransmitter creates bundle {}'.format(self.env.now, bundle))
            self.records[bundle] = self.t
            
            # Get the priority
            priority = int(random() < self.prob_blk)
            
            # If blocking is True, then use yield from
            if self.blocking == True:
                #yield from self.next_obj.transmit(bundle, priority)  (won't work with old python)
                yield self.env.process(self.fun(bundle, priority))
            else:
                self.env.process(self.fun(bundle, priority))
            
            bundle += 1    
        
class Receiver(Simulable):
    def __init__(self, env):
        super().__init__(env, log=True)
        self.records = {}
        
    def put(self, bundle):
        print('t={:3f}:\tSink receives bundle {}'.format(self.env.now, bundle))
        self.records[bundle] = self.t
        
    def get(self, neighbor, bundle):
        """ Just to not break compatibility in DtnNeighborManager """
        self.put(bundle)
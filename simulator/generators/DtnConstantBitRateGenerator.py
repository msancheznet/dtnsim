import numpy as np
from simulator.core.DtnBundle import Bundle
from simulator.generators.DtnAbstractGenerator import DtnAbstractGenerator

class DtnConstantBitRateGenerator(DtnAbstractGenerator):

    def initialize(self):
        # Get generator properties
        self.datarate = self.props.rate
        self.duration = self.props.until
        self.tstart   = self.props.tstart

        # Get bundle properties
        self.data_type  = self.props.data_type
        self.bundle_sz  = self.props.bundle_size
        self.bundle_lat = self.props.bundle_TTL
        self.critical   = self.props.critical

        # Get origin and destination
        self.orig = self.parent.nid
        self.dest = self.props.destination

        # Get the flow id for this generator
        self.assign_fid()

        # Run generator
        self.env.process(self.run())

    def run(self):
        # How often a bundle should be released
        dt = self.bundle_sz / self.datarate

        # Wait until it is time to start this flow
        yield self.env.timeout(self.tstart)

        while self.is_alive:
            # Create a new bundle and record it
            new_bundle = Bundle(self.env, self.orig, next(self.destination()),
                                self.data_type, self.bundle_sz, self.bundle_lat,
                                self.critical, fid=self.fid, TTL=self.bundle_lat)

            # Monitor the new bundle creation
            self.monitor_new_bundle(new_bundle)

            # Log the new bundle creation
            self.disp('{} is created at node {}', new_bundle, self.parent.nid)

            # Schedule routers of bundle
            self.parent.forward(new_bundle)

            # Wait until next time to transmit
            yield self.env.timeout(dt)

            # If you exceed this generator's duration, exit
            if self.t >= self.tstart+self.duration: break

    def predicted_data_vol(self):
        return self.datarate*self.duration

    def destination(self):
        # Get list of possible destination nodes
        nodes = list(self.env.nodes.keys())

        while self.is_alive:
            if self.dest:
                yield self.dest
            else:
                yield nodes[np.random.randint(0, len(nodes))]



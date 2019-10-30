import numpy as np
from simulator.core.DtnBundle import Bundle
from simulator.generators.DtnAbstractGenerator import DtnAbstractGenerator

class DtnFileBroadcaster(DtnAbstractGenerator):

    def initialize(self):
        # Get generator properties
        self.file_sz = self.props.size      # in [bits]
        self.tstart  = self.props.tstart    # in [sec] from start of simulation.
        self.nodes   = list(self.env.nodes.keys())
        self.nodes.remove(self.parent.nid)

        # Get bundle properties
        self.data_type  = self.props.data_type
        self.bundle_sz  = self.props.bundle_size
        self.bundle_lat = self.props.bundle_TTL
        self.critical   = self.props.critical
        self.repeat     = self.props.repeat
        self.wait       = self.props.wait

        # Get origin for all bundles
        self.orig = self.parent.nid

        # Compute how many bundles to generate
        self.Nbnd = int(np.ceil(self.file_sz / self.bundle_sz))

        # Run generator
        self.env.process(self.run())

    def run(self):
        # Wait until it is time to start this flow
        yield self.env.timeout(self.tstart)

        # Send file as many times as needed
        for i in range(self.repeat):
            # Since DTN does not have multi-cast routing, just create
            # copies of bundle to destination
            for destination in self.nodes:
                # Send as many bundles as needed
                for j in range(self.Nbnd):
                    # Create a new bundle and record it
                    new_bundle = Bundle(self.env, self.orig, destination, self.data_type,
                                        self.bundle_sz, self.bundle_lat, self.critical,
                                        fid=(self.orig, destination, self.fid, i, j),
                                        TTL=self.bundle_lat)

                    # Monitor the new bundle creation
                    self.monitor_new_bundle(new_bundle)

                    # Log the new bundle creation
                    self.disp('{} is created at node {}', new_bundle, self.parent.nid)

                    # Schedule routers of bundle
                    self.parent.forward(new_bundle)

            # Wait for a while before sending the file again
            yield self.env.timeout(self.wait)

    def predicted_data_vol(self):
        return len(self.nodes)*self.bundle_sz*self.repeat
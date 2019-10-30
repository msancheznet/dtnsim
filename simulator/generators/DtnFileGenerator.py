import numpy as np
import random
from simulator.core.DtnBundle import Bundle
from simulator.generators.DtnAbstractGenerator import DtnAbstractGenerator

class DtnFileGenerator(DtnAbstractGenerator):

    def initialize(self):
        # Get generator properties
        self.file_sz = self.props.size      # in [bits]
        self.tstart  = self.props.tstart    # in [sec] from start of simulation.

        # Get bundle properties
        self.data_type  = self.props.data_type
        self.bundle_sz  = self.props.bundle_size
        self.bundle_lat = self.props.bundle_TTL
        self.critical   = self.props.critical
        self.repeat     = self.props.repeat
        self.wait       = self.props.wait

        # Get origin and destination
        self.orig = self.parent.nid
        self.dest = self.props.destination

        # Compute how many bundles to generate
        self.Nbnd = int(np.ceil(self.file_sz / self.bundle_sz))

        # Run generator
        self.env.process(self.run())

    def run(self):
        # Wait until it is time to start this flow
        yield self.env.timeout(self.tstart)

        # Initialize variables
        nodes = list(self.env.nodes.keys())
        nodes.remove(self.parent.nid)

        # Get random indices if necessary
        if not self.dest:
            rnd_idx = np.random.randint(0, high=len(nodes), size=(self.repeat,))

        # Send file as many times as needed
        for i in range(self.repeat):
            # Choose destination at random
            dest = self.dest if self.dest else nodes[rnd_idx[i]]

            # Create all the bundles for this file at once
            for _ in range(self.Nbnd):
                # Create the new bundle
                new_bundle = self.new_bundle(dest)

                # Monitor the new bundle creation
                self.monitor_new_bundle(new_bundle)

                # Log the new bundle creation
                self.disp('{} is created at node {}', new_bundle, self.parent.nid)

                # If the node is no longer alive, you are done
                if self.is_alive == False:
                    yield self.env.exit()

                # Schedule routers of bundle
                self.parent.forward(new_bundle)

            # Wait for a while before sending the file again
            yield self.env.timeout(self.wait)

    def predicted_data_vol(self):
        return self.Nbnd*self.bundle_sz*self.repeat

    def new_bundle(self, dest):
        return Bundle(self.env, self.orig, dest, self.data_type,
                      self.bundle_sz, self.bundle_lat, self.critical,
                      fid=self.fid, TTL=self.bundle_lat)
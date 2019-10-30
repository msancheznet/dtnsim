from collections import defaultdict
from .DtnAbstractMobilityModel import DtnAbstractMobilityModel
import numpy as np
import pandas as pd
import itertools
from scipy.spatial.distance import pdist

class DtnRandomWaypointMobilityModel(DtnAbstractMobilityModel):

    def __init__(self, env, props):
        # Call parent constructor
        super(DtnRandomWaypointMobilityModel, self).__init__(env, props)

        # Get model parameters
        self.x_max    = props.x_max
        self.y_max    = props.y_max
        self.v_max    = props.v_max
        self.v_min    = props.v_min
        self.wait_min = props.wait_min
        self.wait_max = props.wait_max
        self.dt       = props.time_step
        self.until    = props.until

        # Get the positions of all nodes over time
        self.pos   = self.compute_positions()
        self.times = pd.unique(self.pos.index.get_level_values(0))

        # Get the pairwise distance between all positions
        self.dist  = self.compute_distances()

    def compute_positions(self):
        # Initialize variables
        pos = defaultdict(dict)

        # Create function to get random node target
        tgt_x_fun = lambda: np.random.uniform(low=0, high=self.x_max)
        tgt_y_fun = lambda: np.random.uniform(low=0, high=self.y_max)

        # Create function to get random node speed
        vel_fun = lambda: np.random.uniform(low=self.v_min, high=self.v_max)

        # Create function to get random node wait time
        wait_fun = lambda: np.random.uniform(low=self.wait_min, high=self.wait_max)

        # Iterate over nodes
        for i, node in enumerate(self.env.nodes):
            # Get initial position, direction and travel distance
            cur_x, cur_y = tgt_x_fun(), tgt_y_fun()
            new_x, new_y = tgt_x_fun(), tgt_y_fun()
            wait, vel    = wait_fun(), vel_fun()
            time = 0.0

            # This node has a 50% chance of starting on a wait
            # period or on a movement period
            if np.random.uniform() <= 0.5: wait = 0.0

            # Compute initial direction to travel
            ang = np.arctan2(new_y - cur_y, new_x - cur_x)

            # Perform simulation
            while time <= self.until:
                # Record current position
                pos[time, node]['x'] = cur_x
                pos[time, node]['y'] = cur_y

                # Update time
                time += self.dt

                # If you need to wait, remain static
                if wait > 0:
                    wait -= self.dt
                    continue

                # Update position
                dx, dy = vel * self.dt * np.cos(ang), vel * self.dt * np.sin(ang)
                cur_x, cur_y = cur_x + dx, cur_y + dy

                # Ensure that you stay within bounds
                cur_x = max(0, min(cur_x, self.x_max))
                cur_y = max(0, min(cur_y, self.y_max))

                # If you are far from your next destination continue
                if np.sqrt((new_x-cur_x)**2 + (new_y-cur_y)**2) > vel*self.dt:
                    continue

                # Select a new position to move to
                new_x, new_y = tgt_x_fun(), tgt_y_fun()

                # Decide how long to wait for and how fast to travel
                wait, vel = wait_fun(), vel_fun()

                # Compute the new direction to travel
                ang = np.arctan2(new_y-cur_y, new_x-cur_x)

        # Transform data frame
        pos = pd.DataFrame.from_dict(pos, orient='index')
        pos.index.rename(('time', 'node'), inplace=True)

        return pos

    def compute_distances(self):
        # Initialize variables
        N     = len(self.env.nodes)
        nodes = list(self.env.nodes)
        combs =  itertools.combinations(range(N), 2)
        combs = [(nodes[i], nodes[j]) for i, j in combs]

        # Depack for faster processing and compute distances. This is essentially
        # doing a groupby('time'), but much faster
        pos_idx = self.pos.index
        pos_vls = self.pos.values
        dist = np.zeros((len(combs), len(self.times)))
        for t in self.times: dist[:, int(t)] = pdist(pos_vls[pos_idx.get_loc(t), :])

        # Dictionary such that dist['N1','N2'] = time series of distances
        dist = {(o, d): dist[i, :] for i, (o, d) in enumerate(combs)}

        return dist
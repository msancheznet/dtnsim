from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs
import pandas as pd

class DtnInLimboBundlesReport(DtnAbstractReport):

    _alias = 'in_limbo'

    def collect_data(self):
        # Initialize variables
        res = {}

        # Iterate over nodes
        for nid, node in self.env.nodes.items():
            q = node.limbo_queue

            # No items in this queue
            if not any(q.items):
                continue

            # The first element of the item is the bundle in the limbo queue
            d = {i: d[0].to_dict() for i, d in enumerate(q.items)}

            # Save data
            res[nid] = pd.DataFrame.from_dict(d, orient='index')

        # Get the bundles stored in all the node's radios
        df = concat_dfs(res, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
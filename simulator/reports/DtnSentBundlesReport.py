import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnSentBundlesReport(DtnAbstractReport):

    _alias = 'sent'

    def collect_data(self):
        # Initialize data
        data = {}

        # Iterate through all nodes
        for nid, node in self.env.nodes.items():
            # If no generators in this node, return
            if not node.generators: data[nid] = pd.DataFrame(); continue

            # Get all the bundles sent
            sent = concat_dfs({gid: gen.list_bundles() for gid, gen in node.generators.items()}, 'generator_id')

            # Store data
            data[nid] = sent

        # Create the total data frame
        df = concat_dfs(data, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
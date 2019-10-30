import pandas as pd
from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnArrivedBundlesReport(DtnAbstractReport):

    _alias = 'arrived'

    def collect_data(self):
        # Get all the bundles that arrived in this node
        df = concat_dfs({nid: pd.DataFrame(bundle.to_dict() for bundle in node.endpoints[0])
                              for nid, node in self.env.nodes.items()}, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
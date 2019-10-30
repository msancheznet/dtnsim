from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnInRadioBundlesReport(DtnAbstractReport):

    _alias = 'in_radio'

    def collect_data(self):
        # Get the bundles stored in all the node's radios
        df = concat_dfs({nid: concat_dfs({rid: r.stored for rid, r in node.radios.items()}, 'radio')
                         for nid, node in self.env.nodes.items()}, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
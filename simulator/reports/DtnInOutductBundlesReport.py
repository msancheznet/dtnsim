from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnInOutductBundlesReport(DtnAbstractReport):

    _alias = 'in_outduct'

    def collect_data(self):
        # Get the bundles stored in all the node's neighbor queues
        df = concat_dfs({nid: concat_dfs({(n, b, t): d.stored for n, v in node.ducts.items()
                                          for b, vv in v.items() for t, d in vv.items()},
                                         ('neighbor', 'band', 'duct_type', 'idx'))
                                          for nid, node in self.env.nodes.items()}, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
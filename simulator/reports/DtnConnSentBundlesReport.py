from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnConnSentBundlesReport(DtnAbstractReport):

    _alias = 'transmitted'

    def collect_data(self):
        # Get the bundles lost in a connection
        df = concat_dfs({cid: conn.list_sent() for cid, conn in self.env.connections.items()},
                        'connection')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df
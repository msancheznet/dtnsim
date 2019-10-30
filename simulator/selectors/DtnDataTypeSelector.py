from simulator.selectors.DtnAbstractDuctSelector import DtnAbstractDuctSelector

class DtnDataTypeSelector(DtnAbstractDuctSelector):
    """ This outduct selector can be used for connections with 2 or 3 simultaneous
        frequency bands. It behaves as follows:

        1) If 2 frequency bands, they must be named 'X' and 'Ka'. Biomedical and voice
           data are sent over the X-band link, while the rest goes through Ka-band
        2) If 3 frequency bands, they must be named 'X', 'Ka' and 'opt'. Biomedical and voice
           data are sent over the X-band link. Ka-band is used for non-critical data
           except for "PAO HD Video", "Sci HD Video" and "Science", which are sent over
           the optical link.
    """
    def select_duct(self, neighbor, bundle):
        # Get the ducts from the parent
        ducts = self.get_ducts(neighbor)

        # If only one band, just return it
        if len(ducts) == 1: return next(iter(ducts.values()))

        # If two bands, assume X and Ka
        if len(ducts) == 2: return ducts[self.select_biband(bundle)]

        # If three bands, assume X, Ka and optical
        if len(ducts) == 3: return ducts[self.select_triband(bundle)]

        # More than three bands is not supported by this class
        # You need to define a new one
        raise ValueError(f'Connections with no outducts or more than 3 outducts concurrently '
                         f'are not supported. Check connection between {self.parent.nid} '
                         f'and {neighbor}.')

    def select_biband(self, bundle):
        return 'X' if bundle.data_type.lower() in ['biomedical', 'voice'] else 'Ka'

    def select_triband(self, bundle):
        if bundle.data_type.lower() in ['biomedical', 'voice']:
            return 'X'
        if bundle.data_type.lower() not in ['pao hd video', 'sci hd video', 'science']:
            return 'Ka'
        return 'opt'
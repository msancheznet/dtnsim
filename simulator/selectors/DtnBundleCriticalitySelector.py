# -*- coding: utf-8 -*-

from simulator.selectors.DtnAbstractDuctSelector import DtnAbstractDuctSelector

class DtnBundleCriticalitySelector(DtnAbstractDuctSelector):
    """ This outduct selector can be used for connections with 2 or 3 simultaneous
        frequency bands. It behaves as follows:

            1) If 2 frequency bands, they must be named 'X' and 'Ka'. All critical data
               is sent over the X-band link and the rest over the Ka-band link.
            2) If 3 frequency bands, they must be named 'X', 'Ka' and 'opt'. All critical
               data is sent over the X-band link. Ka-band is used for non-critical data
               except for "PAO HD Video", "Sci HD Video" and "Science", which are sent over
               the optical link.
    """
    def select_duct(self, neighbor, bundle):
        # Get the outducts from the parent
        ducts = self.get_ducts(neighbor)

        # If only one band, just return it
        if len(ducts) == 1: return next(iter(ducts.values()))

        # If two bands, assume X and Ka
        if len(ducts) == 2: return ducts[self.select_biband(bundle)]

        # If three bands, assume X, Ka and optical
        if len(ducts) == 3: return ducts[self.select_biband(bundle)]

        # More than three bands is not supported by this class
        # You need to define a new one
        raise ValueError(f'Connections with more than 3 outducts concurrently are '
                         f'not supported. Check connection between {self.parent.nid} '
                         f'and {neighbor}.')

    def select_biband(self, bundle):
        return 'X' if bundle.critical else 'Ka'

    def select_triband(self, bundle):
        if bundle.critical == True:
            return 'X'
        if bundle.data_type.lower() not in ['pao hd video', 'sci hd video', 'science']:
            return 'Ka'
        return 'opt'


class DtnBandSelectorOld(DtnAbstractDuctSelector):

    def select_band(self, bundle, orig, dest):
        # Initialize variables
        con_type = self._types[orig][dest]

        # Assign band as a function of connection and data type
        if   con_type == 'UniBand':     return 'SA'
        elif con_type == 'BiBand':      return self._assign_BiBand_band(bundle)
        elif con_type == 'BiBandLTP':   return self._assign_BiBand_band(bundle)
        """if   con_type == 'UniDTE': return 'X'
        elif con_type == 'BiDTE':  return self._assign_BiDTE_band(bundle)
        elif con_type == 'TriDTE': return self._assign_TriDTE_band(bundle)"""

        # Just return the same connection type
        return con_type

    def _assign_BiBand_band(self, bundle):
        #return 'X' if bundle.critical else 'Ka'
        return 'X' if bundle.data_type.lower() == 'biomedical' else 'Ka' # FOR TESTING

    """def _assign_BiDTE_band(self, bundle):
        return 'X' if bundle.critical else 'Ka'

    def _assign_TriDTE_band(self, bundle):
        if bundle.critical == True:
            return 'X'
        if bundle.data_type not in ['PAO HD Video', 'Sci HD Video', 'Science']:
            return 'Ka'
        return 'opt'"""
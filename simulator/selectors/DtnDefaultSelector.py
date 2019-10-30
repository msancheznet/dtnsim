from simulator.selectors.DtnAbstractDuctSelector import DtnAbstractDuctSelector

class DtnDefaultSelector(DtnAbstractDuctSelector):
    """ The default duct selector. It can only be used for the connection
        that only have one duct running over them.

        .. warning:: If you try to use this selector in a connection with more
                     than one outduct, an exception will be raised
    """

    def select_duct(self, neighbor, bundle):
        # Get the outducts from the parent
        ducts = self.get_ducts(neighbor)

        # If there is more than one duct available, throw error.
        # You cannot use the default selector
        if len(ducts) > 1:
            raise ValueError(f'Cannot use "DtnDefaultSelector" if more than outduct available.\n'
                             f'Check outducts from {self.parent.nid} to {neighbor}')

        # Assign the duct directly
        return next(iter(ducts.values()))




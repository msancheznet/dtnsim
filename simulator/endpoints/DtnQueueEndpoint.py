from simulator.endpoints.DtnAbstractEndpoint import DtnAbstractEndpoint

class DtnQueueEndpoint(DtnAbstractEndpoint):

    def __bool__(self):
        return bool(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def initialize(self, *args, **kwargs):
        self.data = self.parent.queues['opportunistic'].handshake_queue

    def put(self, *args, **kwargs):
        self.env.process(self.do_put(*args, **kwargs))

    def do_put(self, *args, **kwargs):
        yield from self.data.put(*args, **kwargs)
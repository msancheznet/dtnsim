from simulator.radios.DtnVariableRadio import DtnVariableRadio

class NwcVariableRadio(DtnVariableRadio):
    def run(self):
        while self.is_alive:
            # Get the next segment to transmit
            item = yield from self.in_queue.get()

            # Depack item
            neighbor, message, peer, direction = item

            # Wait until this connection is active
            if self.active[neighbor].is_red:
                yield self.active[neighbor].green

            # Get the connection to send this message through
            conn = self.outcons[neighbor]

            # Get the data rate for this radio
            tx_time = self.get_tx_time(neighbor, message)

            # Apply delay for radio to transmit entire segment
            yield self.env.timeout(tx_time)

            # If the node is no longer alive, you are done
            if not self.is_alive:
                continue

            # Count the energy consumed
            self.parent.battery -= self.parent.P_radio * tx_time

            # Transmit the message through the connection.
            self.send_through_connection(message, conn, peer, direction)
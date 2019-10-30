from fractions import Fraction
import numpy as np
from simulator.radios.DtnBasicRadio import DtnBasicRadio

class DtnCodedRadio(DtnBasicRadio):
    """ Simulate a radio with a given coding scheme. Note that in reality
        frames are not generated, only the equivalent BER to achieve the
        specified FER is calculated given the frame size, code rate and mesage
        size.

        This radio is only an approximation. If a message is very short (e.g.
        10 bytes), a real radio would aggregate multiple messages into a frame
        prior to sending anything. This is not modeled in this case, the very
        short message is sent immediately as is.
    """
    def initialize(self, rate=0, FER=0, frame_size=0, code_rate=0,
                   J_bit=0, **kwargs):
        # Store configuration parameters
        self.datarate = float(rate)
        self.FER = float(FER)
        self.frame_size = float(frame_size)
        self.code_rate = float(Fraction(code_rate))
        self.J_bit = float(J_bit)

        # Call grand-parent initializer
        super(DtnBasicRadio, self).initialize()

    def send_through_connection(self, message, conn, peer, direction):
        # Compute the equivalent BER that yields this radio's FER
        BER = self.compute_equivalent_BER(message)

        # This is a non-blocking call since the bundle is out in transit
        conn.transmit(peer, message, BER, direction=direction)

    def compute_equivalent_BER(self, message):
        # Compute total number of bits to send with coding
        num_bits = message.num_bits/self.code_rate

        # Compute the number of frames to send this message
        N = np.ceil(num_bits/self.frame_size)

        # Compute probability of tx the message ok
        prob_msg_ok = (1-self.FER)**N

        # Compute the equivalent BER
        return (1-(prob_msg_ok**(self.code_rate/message.num_bits)))


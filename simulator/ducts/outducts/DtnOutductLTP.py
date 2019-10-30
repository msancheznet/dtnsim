from simulator.ducts.DtnAbstractDuctLTP import DtnAbstractDuctLTP
from simulator.core.DtnPriorityQueue import DtnPriorityQueue
from simulator.core.DtnSegments import LtpDataSegment
from simulator.core.DtnSegments import LtpReportAcknowledgementSegment
from simulator.core.DtnSegments import LtpCancelSessionSegment
import numpy as np
import pandas as pd
from simulator.utils.math_utils import union_intervals

class DtnOutductLTP(DtnAbstractDuctLTP):
    """ An LTP Outduct """
    duct_type = 'outduct'

    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnOutductLTP, self).__init__(env, name, parent, neighbor)

        # Checkpoint counter to create unique checkpoints per block
        self.checkpoint_counter = {}

        # Stores current block, segments and checkpoint under transmission
        self.block      = {}
        self.checkpoint = {}

    @property
    def stored(self):
        df = self.radio.stored
        d = {}
        for sid, q in self.ltp_queues.items():
            dff = q.stored
            if dff.empty: continue
            dff['where'] = 'LTP session {}'.format(sid)
            d[sid] = dff
        return pd.concat(pd.concat(d), df) if d else df

    def initialize(self, peer, *args, agg_size_limit=1e9, agg_time_limit=1e9, segment_size=8e6,
                   checkpoint_timer=1e10, **kwargs):
        """ Units of inputs are bits and seconds """
        # Call parent initialization
        super(DtnOutductLTP, self).initialize(peer, **kwargs)

        # The aggregation size and time limits to construct a bundle
        self.agg_size_limit = float(agg_size_limit)
        self.agg_time_limit = float(agg_time_limit)

        # The LTP segment size
        self.segment_size = float(segment_size)

        # Checkpoint timer. How long to wait until you resend the checkpoint segment
        self.checkpoint_timer = float(checkpoint_timer)

    def run(self):
        """ Creates an LTP block from a set of bundles and sends them """
        # Initialize variables
        cur_block_size = 0.0
        last_block_time = 0.0
        cur_block = []

        while self.is_alive:
            # Wait until there is something to transmit
            bundle = yield from self.in_queue.get()

            # Add bundle to block
            cur_block.append(bundle)

            # Compute total size of this block and the time since last block was issued
            cur_block_size += bundle.data_vol                   # bits
            delta_t         = self.env.now - last_block_time

            # If the aggregation size limit has not been exceeded, continue
            if cur_block_size < self.agg_size_limit and delta_t < self.agg_time_limit:
                continue

            # Transform block to tuple to make it hashable. Also, from now on it should not
            # change anymore
            cur_block  = tuple(cur_block)
            session_id = self.get_session_id(cur_block)

            # Initialize an LTP session to transmit this block
            self.initialize_ltp_session(session_id, cur_block, cur_block_size)

            # Reset block counters
            cur_block_size = 0.0
            last_block_time = 0.0
            cur_block = []

    def initialize_ltp_session(self, session_id, block, size):
        # Store the block and create an acknowledgement queue for that session
        self.block[session_id]      = block
        self.ltp_queues[session_id] = DtnPriorityQueue(self.env)

        # Initialize the checkpoint counter for this session. All checkpoints
        # must have a unique value
        self.checkpoint_counter[session_id] = 0

        # Start the session timer. If the transaction has not been completed by then
        # the bundles in this block need to be re-routed
        self.env.process(self.start_session_timer(session_id))

        # Start the process for managing this LTP session
        # Note: This is a non-blocking call since you can have multiple LTP sessions
        #       running at the same time
        self.env.process(self.run_ltp_session(session_id, size))

    def finalize_ltp_session(self, session_id):
        # Delete global variables for this session
        block = self.block.pop(session_id)
        self.checkpoint.pop(session_id)
        self.checkpoint_counter.pop(session_id)
        self.ltp_queues.pop(session_id)

        return block

    def run_ltp_session(self, session_id, size):
        # Initialize variables
        reports  = set()    # Report segments seen during this LTP session
        acked    = 0.0      # Counts how many bits of the block have been acknowledged
        success  = False    # If True, then LTP succeeded in sending the entire block

        # If this flag is true, then proceed with sending the segments. The first time around
        # this is always true
        do_send = True

        # Create initial list of segment to transmit
        segments, checkpoint = self.get_data_segments(session_id, size)

        # Store the current checkpoint
        self.checkpoint[session_id] = checkpoint

        # Run until all bits in this block have been acknowledged
        while self.is_alive:
            # If you have permission to send, go ahead and do it
            if do_send:
                # Start transmitting all segments
                for s in segments: self.radio.put(self.neighbor, s, self.peer, self.transmit_mode)

                # Start the timer for the checkpoint report receive
                self.env.process(self.start_checkpoint_timer(session_id, checkpoint))

                # Mark do_send as false, to avoid re-sending these segments if the report
                # segment has errors
                do_send = False

            # Wait until you get a report segment. Note that this implementation, waiting
            # for the RS here is representative **only** of the deferred-ack mode
            report = yield from self.ltp_queues[session_id].get()

            # Check if the report received is correct. If it is not, then go back to waiting for
            # report segment but do not re-send the segments (you have already done it)
            if report.has_errors: continue

            # If this is a Cancel Segment report, then exit
            if report.type == 'CS':
                break

            # Acknowledge report before checking if you have seen it since this can indicate
            # that the previous report acknowledgement was lost
            self.acknowledge_report(session_id, report)

            # If this report segment was already received, you are done
            if report in reports: continue

            # Process this new report and save it
            acked += self.process_report(report)
            reports.add(report)

            # If the total number of bytes acknowledged equals the block size, you are done
            if acked >= size: success = True; break

            # Create segments to transmit because of this report
            segments, checkpoint = self.get_data_segments(session_id, size-acked, report_id=report.id)

            # Update the current checkpoint
            self.checkpoint[session_id] = checkpoint

            # Mark do_send as True since you have new segments to send
            do_send = True

        # Tear down this LTP session
        block = self.finalize_ltp_session(session_id)

        # If you succeeded, you are done
        if success:
            for bundle in block: yield from self.success_queue.put(bundle)
            return

        # If this LTP session did not succeed, the bundles need to go to the node's limbo
        for bundle in block:
            yield from self.to_limbo.put(bundle)

    def acknowledge_report(self, session_id, report):
        # Create the acknowledge report
        segment = LtpReportAcknowledgementSegment(session_id, report.id)

        # Send for transmission
        self.radio.put(self.neighbor, segment, self.peer, self.transmit_mode)

    def process_report(self, report):
        # Get the report bounds
        lb, ub = report.lower_bnd, report.upper_bnd

        # Get the report claims sections
        offset, length = zip(*report.claims)

        # Transform to numpy arrays
        start = np.array(offset)
        end   = start + np.array(length)

        # Compute the data intervals that these claims acknowledge
        start, end = union_intervals(offset, end, stacked=False)

        # Make sure that you stay within the bounds
        start, end = np.maximum(start, lb), np.minimum(end, ub)

        # Compute the total data volume acknowledged by the claims
        return np.sum(end-start)

    def get_data_segments(self, session_id, size, report_id=None):
        """ Create new segments to send ``size`` bytes of data from the block ``bid``.
            This function assumes deferred-acked mode of operations, so a checkpoint
            is only defined for the last segment.

            :param session_id: LTP session id (one session per block)
            :param size: Size in bytes of the block
            :return tuple: (List of segments to transmit, checkpoint segment)
        """
        # Initialize variables
        miss  = size
        N     = int(np.ceil(miss / self.segment_size))    # Number of segments
        to_tx = []

        # Create segments
        for i in range(N):
            if i == N-1:
                checkpt = self.checkpoint_counter[session_id]
                self.checkpoint_counter[session_id] += 1
            else:
                checkpt = None

            length  = min(miss, self.segment_size)
            segment = LtpDataSegment(session_id, i * self.segment_size, length,
                                     checkpoint=checkpt, report=report_id)
            miss   -= length
            to_tx.append(segment)

        return to_tx, to_tx[-1]

    def start_checkpoint_timer(self, session_id, old_checkpoint):
        # Wait until timer expires
        yield self.env.timeout(self.checkpoint_timer)

        # If this session id is no longer present, then this LTP session has
        # already ended. Just return
        if not self.is_session(session_id): return

        # Get the current checkpoint being processed
        cur_checkpoint = self.checkpoint[session_id]

        # If the checkpoint that triggered the timer is not the current
        # checkpoint, then this timer is not needed
        if cur_checkpoint.checkpoint != old_checkpoint.checkpoint: return

        # Reset the ``has_errors`` flag
        old_checkpoint.has_errors = False

        # If the checkpoint that triggered the timer is still the current
        # checkpoint, then re-transmit the checkpoint segment (i.e. the last one)
        self.radio.put(self.neighbor, old_checkpoint, self.peer, self.transmit_mode)

        # Start the timer for the checkpoint report receive
        self.env.process(self.start_checkpoint_timer(session_id, old_checkpoint))

    def start_session_timer(self, session_id):
        # Wait for 1 day, after that you should have succeeded
        yield self.env.timeout(24 * 60 * 60)

        # If this session already ended successfully, skip
        if not self.is_session(session_id): return

        # Cancel the LTP session
        self.cancel_ltp_session(session_id)

    def do_ack(self, segment):
        """ Re-implement to enable reception of Report Segments """
        self.disp('{} delivered to {} through ACK', segment, self.__class__.__name__)

        # Get session id
        sid = segment.session_id

        # If there is no ltp_queue for this message's session, then the outduct
        # thinks that this transmission was already successful. Therefore, just
        # send a report acknowledgement automatically.
        # This can happen if the RA for the last RS is lost, and the LTP induct
        # re-sends the last RS after a long enough timeout.
        if sid not in self.ltp_queues:
            self.acknowledge_report(sid, segment)
            return

        # Process the message normally by adding to the LTP queue of acknowledgements
        # Since this is a normal report segment, use priority 1.
        yield from self.ltp_queues[segment.session_id].put(segment, 1)

    def __str__(self):
        return "<LtpOutduct {}-{}>".format(self.parent.nid, self.neighbor)
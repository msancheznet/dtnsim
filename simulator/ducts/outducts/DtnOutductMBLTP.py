from copy import deepcopy
import numpy as np
import pandas as pd
from simulator.core.DtnPriorityQueue import DtnPriorityQueue
from simulator.core.DtnSegments import LtpDataSegment
from simulator.core.DtnSegments import LtpReportAcknowledgementSegment
from simulator.ducts.DtnAbstractDuctMBLTP import DtnAbstractDuctMBLTP
from simulator.utils.math_utils import union_intervals, xor_intervals

class DtnOutductMBLTP(DtnAbstractDuctMBLTP):
    duct_type = 'outduct'

    def __init__(self, env, name, parent, neighbor):
        # Call parent constructor
        super(DtnOutductMBLTP, self).__init__(env, name, parent, neighbor)

        # Checkpoint counter to create unique checkpoints per block
        self.checkpoint_counter = {}

        # Stores current block, segments and checkpoint under transmission
        self.block      = {}
        self.checkpoint = {}

    @property
    def stored(self):
        df = pd.concat({b: self.radio[b].stored for b in self.bands})
        df['where'] = 'radio'
        d = {}
        for sid, q in self.ltp_queues.items():
            dff = q.stored
            if dff.empty: continue
            dff['where'] = 'LTP session {}'.format(sid)
            d[sid] = dff
        return pd.concat(pd.concat(d), df) if d else df

    def initialize(self, peer, bands=None, agg_size_limit=1e9, agg_time_limit=1e9, segment_size=8e6,
                   checkpoint_timer=1e10, **kwargs):
        # Call parent initialization
        super(DtnOutductMBLTP, self).initialize(peer, bands=bands, **kwargs)

        # The aggregation size and time limits to construct a bundle
        self.agg_size_limit = float(agg_size_limit)
        self.agg_time_limit = float(agg_time_limit)

        # The LTP segment size
        self.segment_size = float(segment_size)

        # Checkpoint timer. How long to wait until you resend the checkpoint segment
        self.checkpoint_timer = float(checkpoint_timer)

    def run(self):
        """ Creates an LTP block from a set of bundles and sends them. This is the same
            as for a normal LTP outduct
        """
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
            cur_block_size += bundle.data_vol  # bits
            delta_t = self.env.now - last_block_time

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

        # Return the block in case you have to put it to the limbo
        # because this session failed
        return block

    def run_ltp_session(self, session_id, size):
        # Initialize variables
        acked   = 0.0             # Number of bits in this block acknowledged
        reports = set()           # Report segments seen during this LTP session
        success = False           # If True, then LTP succeeded in sending the entire block

        # If this flag is true, then proceed with sending the segments. The first time around
        # this is always true
        do_send = True

        # Create initial list of segment to transmit
        segments, checkpoint = self.get_new_block_segment(session_id, size)

        # Store the current checkpoint
        self.checkpoint[session_id] = checkpoint

        # Run until all bits in this block have been acknowledged
        while self.is_alive:
            # If you have permission to send, go ahead and do it
            if do_send:
                # Start transmitting all segments
                for s in segments: self.send_through_all(s)

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
            if report.type == 'CS': break

            # If this report segment was already received, you are done. Otherwise, mark it
            # as already seen
            if report.id in reports: continue
            reports.add(report.id)

            # Acknowledge report before checking if you have seen it since this can indicate
            # that the previous report acknowledgement was lost
            self.acknowledge_report(session_id, report)

            # Compute the total data volume acknowledged by this report. Note that you could
            # receive a report that acks less data than another that arrived before
            acked = max(acked, self.process_report(report))

            # If the total number of bytes acknowledged equals the block size, you are done
            if acked >= size: success = True; break

            # Create segments to transmit because of this report
            segments, checkpoint = self.get_missing_block_segments(session_id, report)

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

        # If this LTP session did not succeed, send bundles to node's limbo
        for bundle in block:
            yield from self.to_limbo.put(bundle)

    def acknowledge_report(self, session_id, report):
        # Create the acknowledge report
        segment = LtpReportAcknowledgementSegment(session_id, report.id)

        # Send for transmission
        self.send_through_all(segment)

    def process_report(self, report):
        # Claims have already been run through the union_set_intervals
        # at the induct. Just return the data volume
        return sum(claim[1] for claim in report.claims)

    def get_new_block_segment(self, session_id, size):
        # Compute number of segments to send block
        N = int(np.ceil(size/self.segment_size))

        # Create new segments
        to_tx = [LtpDataSegment(session_id, i*self.segment_size, self.segment_size)
                 for i in range(N)]

        # Mark the last one as a checkpoint
        to_tx[-1].checkpoint = self.new_checkpoint_id(session_id)

        # Return segments and checkpoint
        return to_tx, to_tx[-1]

    def get_missing_block_segments(self, session_id, report):
        # Compute claims intervals
        offset, length = zip(*report.claims)

        # Compute start and end of intervals
        start = np.array(offset)
        end   = start + np.array(length)

        # Compute which parts of the block are missing
        missing = xor_intervals(report.lower_bnd, report.upper_bnd,
                                start, end, do_union=False, sort=True)

        # Initialize variables
        to_tx = []

        # Create new segments
        for int_s, int_e in missing:
            # Calculate the number of data segments to generated for this
            # piece of missing data
            N = int((int_e-int_s)/self.segment_size)

            # Create the data segments
            new_segs = []
            for i in range(N):
                seg_ini = int_s + i*self.segment_size
                new_segs.append(LtpDataSegment(session_id, seg_ini, self.segment_size,
                                               report=report.id))

            # Save these segments
            to_tx.extend(new_segs)

        # Mark the last one as a checkpoint
        to_tx[-1].checkpoint = self.new_checkpoint_id(session_id)

        # Return segments and checkpoint
        return to_tx, to_tx[-1]

    def new_checkpoint_id(self, session_id):
        # Update the checkpoint counter
        self.checkpoint_counter[session_id] += 1
        return self.checkpoint_counter[session_id]

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
        self.send_through_all(old_checkpoint)

        # Start the timer for the checkpoint report receive
        self.env.process(self.start_checkpoint_timer(session_id, old_checkpoint))

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

    def send_through_all(self, segment):
        """ Send a copy of this segment through all the frequency bands available

            .. Warning:: A new deep copy of the segment is created for each frequency
                         band.
        """
        for i, b in enumerate(self.bands):
            s = segment if i == 0 else deepcopy(segment)
            self.radio[b].put(self.neighbor, s, self.peer, self.transmit_mode)

    def __str__(self):
        return "<MBLtpOutduct {}-{}>".format(self.parent.nid, self.neighbor)
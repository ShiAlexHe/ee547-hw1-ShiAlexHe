from cgitb import handler
from dataclasses import dataclass
from pathlib import Path

from problem3.message_source import MessageSource, Packet


@dataclass
class LoggerStats:
    packets_received: int  # Total packets from source
    packets_written: int  # Packets written to log
    duplicates_discarded: int  # Duplicate packets ignored
    corrupted_packets: int  # Packets with bad checksum
    retransmit_requests: int  # Times request_retransmit called
    retransmits_received: int  # Successful retransmits
    inversions: int  # Out-of-order writes (LATE status)
    gaps: int  # Missing sequences in final log
    buffer_flushes: int  # Times buffer was flushed
    final_buffer_size: int  # Packets in buffer at termination (lost)


class EventLogger:
    def __init__(self,
                 source: MessageSource,
                 log_file: Path,
                 buffer_size: int = 50):
        """
        Initialize event logger.

        Args:
            source: Message source to receive from
            log_file: Path to append-only log file
            buffer_size: Max packets to buffer before forced flush
        """
        self.source = source
        self.log_file = log_file
        self.buffer_size = buffer_size

        # Your state variables
        self.buffer: list[Packet] = []
        self.seen_sequences: set[int] = set()
        self.last_written_seq: int = -1
        self.written=set()
        self.pending_retransmits: set[int] = set()
        self.status= {}
        self.max_receive=-1
        # Add more as needed

    def run(self) -> LoggerStats:
        """
        Main processing loop.

        Continuously receive packets until termination.
        Handle each packet appropriately:
        - Verify checksum (request retransmit if corrupted)
        - Detect duplicates (discard if already seen)
        - Buffer or write based on your strategy
        - Periodically flush buffer

        Returns:
            Statistics about logging performance.
        """
        self.logger = LoggerStats(
            packets_received=0,
            packets_written=0,
            duplicates_discarded=0,
            corrupted_packets=0,
            retransmit_requests=0,
            retransmits_received=0,
            inversions=0,
            gaps=0,
            buffer_flushes=0,
            final_buffer_size=0,
        )

        while True:
            package=self.source.receive()
            if package is None:
                break
            self.max_receive=max(package.sequence,self.max_receive)
            self.logger.packets_received+=1

            if package.sequence in self.pending_retransmits:
                self.logger.retransmits_received+=1

            # Detect duplicates
            if package.sequence in self.seen_sequences:
                self.logger.duplicates_discarded+=1
                continue

            # Verify checksum
            if not self.source.verify_checksum(package):
                self.logger.corrupted_packets+=1
                self.source.request_retransmit(package.sequence)
                self.logger.retransmit_requests+=1
                self.pending_retransmits.add(package.sequence)
                continue

            self.seen_sequences.add(package.sequence)
            if package.sequence in self.pending_retransmits:
                self.pending_retransmits.remove(package.sequence)

            #Buffer or write based on your strategy
            #if good
            if self.last_written_seq+1==package.sequence:
                if package.sequence not in self.status:
                    self.status[package.sequence]='OK'
                self._handle_packet(package)
                continue

            #if late
            elif self.last_written_seq>package.sequence:
                self.status[package.sequence]='LATE'
                self._handle_packet(package)

            elif self.last_written_seq<package.sequence-1:
                if self._should_flush():
                    if self.buffer and package.sequence<self.buffer[0].sequence:#smallest
                        self._handle_packet(package)
                        self._flush_buffer()
                    elif self.buffer and package.sequence>self.buffer[-1].sequence:#biggest
                        if self.buffer[-1].sequence==package.sequence-1:#just right
                            self._flush_buffer()
                            self._handle_packet(package)
                        else:
                            self._flush_buffer()
                            self.buffer.append(package)
                else:
                    self.buffer.append(package)

            expect=self.last_written_seq+1
            expect_in=False
            for i in self.buffer:
                if expect==i.sequence:
                    expect_in=True
                    break
            if expect_in:
                self.buffer.sort(key=lambda x: x.sequence)
                work=False
                while self.buffer and self.buffer[0].sequence == self.last_written_seq + 1:
                    self._handle_packet(self.buffer[0])
                    self.buffer.pop(0)
                    work=True
                if work:
                    self.logger.buffer_flushes+=1
            expect = self.last_written_seq + 1
            if len(self.buffer)>self.buffer_size*0.8 and expect not in self.pending_retransmits:
                self.source.request_retransmit(expect)
                self.logger.retransmit_requests += 1
                self.pending_retransmits.add(expect)
        self.logger.final_buffer_size=len(self.buffer)
        self._finalize()
        self.logger.gaps=self.max_receive-self.logger.packets_written
        return self.logger



    def _handle_packet(self, packet: Packet) -> None:
        """Process a single packet."""
        #sequence,timestamp,payload_hex,status
        if packet.sequence in self.written:
            return
        self.written.add(packet.sequence)
        self.last_written_seq=max(self.last_written_seq,packet.sequence)
        if packet.sequence in self.pending_retransmits:
            self.status[packet.sequence] = 'RETRANSMIT'
            self.pending_retransmits.remove(packet.sequence)
        if packet.sequence not in self.status:
            self.status[packet.sequence]='OK'
        self.logger.packets_written+=1
        if self.status[packet.sequence]=='LATE':
            self.logger.inversions+=1
        with open(self.log_file, "a") as f:
            f.write(f"{packet.sequence}, {packet.timestamp}, {packet.payload.hex()}, {self.status[packet.sequence]}\n")

    def _should_flush(self) -> bool:
        """Determine if buffer should be flushed."""
        self.buffer.sort(key=lambda x: x.sequence)
        if len(self.buffer)==self.buffer_size:
            return True
        return False

    def _flush_buffer(self) -> None:
        """Write buffered packets to log."""
        self.logger.buffer_flushes+=1
        for i in self.buffer:
            if i.sequence<self.last_written_seq:
                self.status[i.sequence]='LATE'
            else:
                self.status[i.sequence]='OK'
            self._handle_packet(i)
        self.buffer.clear()

    def _finalize(self) -> None:
        """Called after termination. Flush remaining buffer."""
        self._flush_buffer()


if __name__=='__main__':
    # Test with different parameters
    source = MessageSource(
        seed=42,
        total_packets=500,
        reorder_window=10,
        duplicate_prob=0.05,
        loss_prob=0.02,
        corruption_prob=0.03,
        termination_rate=0.002
    )

    logger = EventLogger(source, Path("events.log"), buffer_size=30)
    stats = logger.run()
    # print(stats.duplicates_discarded)
    # print(stats.corrupted_packets)
    print(stats.retransmit_requests)
    print(f"Coverage: {stats.packets_written}/{source.total_packets}")
    print(f"Inversions: {stats.inversions}")
    print(f"Lost in buffer: {stats.final_buffer_size}")
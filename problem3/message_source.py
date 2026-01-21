# Provided: message_source.py

from dataclasses import dataclass
import random
import zlib

@dataclass
class Packet:
    sequence: int       # Global sequence number (ground truth order)
    timestamp: float    # Generation timestamp
    payload: bytes      # Arbitrary payload data
    checksum: int       # CRC32 checksum of payload

class MessageSource:
    def __init__(self,
                 seed: int | None = None,
                 total_packets: int = 1000,
                 reorder_window: int = 10,
                 duplicate_prob: float = 0.05,
                 loss_prob: float = 0.02,
                 corruption_prob: float = 0.03,
                 termination_rate: float = 0.001):
        """
        Initialize message source.

        Args:
            seed: Random seed for reproducibility (None for random)
            total_packets: Number of packets to generate
            reorder_window: Max positions a packet can be delayed
            duplicate_prob: Probability of duplicate delivery
            loss_prob: Probability of packet never arriving
            corruption_prob: Probability of corrupted checksum
            termination_rate: Lambda for Poisson termination process
        """
        self.rng = random.Random(seed)
        # ... implementation provided

    def receive(self) -> Packet | None:
        """
        Receive next packet.

        Returns:
            Packet if available, None if terminated.

        Packets may arrive:
        - Out of order (within reorder_window)
        - Duplicated (same sequence number twice)
        - Corrupted (checksum won't match)
        - Never (lost packets leave gaps)

        Process terminates with probability based on termination_rate.
        After termination, receive() always returns None.
        """
        ...

    def request_retransmit(self, sequence: int) -> None:
        """
        Request retransmission of a packet.

        The packet will be re-queued for delivery with:
        - Additional delay (simulating network RTT)
        - Same corruption/loss probability as original

        Use this for:
        - Corrupted packets (checksum mismatch)
        - Suspected lost packets (gap timeout)
        """
        ...

    def verify_checksum(self, packet: Packet) -> bool:
        """Check if packet checksum is valid."""
        return zlib.crc32(packet.payload) == packet.checksum

    def get_ground_truth(self) -> list[int]:
        """
        Get list of all sequence numbers that were generated.
        Only call after termination.
        """
        ...

    def is_terminated(self) -> bool:
        """Check if source has terminated."""
        ...
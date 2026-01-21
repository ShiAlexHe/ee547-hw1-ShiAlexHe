import json
from os import write
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Message:
    msg_type: str   # Max 5 chars
    values: list[int]  # Max 10 integers

@dataclass
class WorkerStats:
    comparisons: int      # Number of comparison operations
    messages_sent: int    # Number of messages written
    messages_received: int # Number of messages read
    values_output: int    # Number of values written to output

class MergeWorker:
    def __init__(self,
                 worker_id: str,        # "A" or "B"
                 data: list[int],       # This worker's sorted data
                 inbox: Path,           # Read messages from here
                 outbox: Path,          # Write messages here
                 output: Path,          # Append merged results here
                 state_file: Path):     # Persist state between steps
        self.worker_id = worker_id
        self.data = data
        self.inbox = inbox
        self.outbox = outbox
        self.output = output
        self.state_file = state_file
        self.stats = WorkerStats(0, 0, 0, 0)

        self.state: dict = self._load_state()

    def _load_state(self) -> dict:
        """Load state from file, or initialize if first run."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return self._initial_state()

    def _save_state(self) -> None:
        """Persist state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)

    def _initial_state(self) -> dict:
        return {
            "phase": "INIT",
            "index":0,
            'len':len(self.data)
            # Add more state variables as needed
        }

    def step(self) -> bool:
        """
        Execute one step of work.

        Returns:
            True if more work remains, False if done.

        Each step should:
        1. Read any messages from inbox (may be empty)
        2. Update internal state
        3. Write any messages to outbox (at most one per step)
        4. Write any finalized values to output
        5. Save state
        """

        def output_till(max_v, include=False):
            nonlocal write
            index, count = self.state['index'], self.state['len']
            with open(self.output, "a") as f:
                while index < count and self.data[index] < max_v:
                    if write:
                        f.write(', ')
                    write=True
                    f.write(f"{self.data[index]}")
                    index += 1
                    self.stats.comparisons += 1
                    self.stats.values_output += 1
            self.state['index'] = index
            if include:
                with open(self.output, "a") as f:
                    if write:
                        f.write(', ')
                    write=True
                    f.write(f"{max_v}")
                    self.stats.values_output += 1
            if index >= count:
                return 'DONE'
            return 'LOCK'

        def read_inbox():
            if not self.inbox.exists():
                return None
            self.stats.messages_received += 1
            with open(self.inbox) as f:
                msg = json.load(f)
            self.inbox.unlink(missing_ok=True)
            return msg

        def write_msg(msg):
            with open(self.outbox, "w") as f:
                json.dump({"msg_type": msg.msg_type, "values": msg.values}, f)
            self.stats.messages_sent += 1

        # load and init
        self.state = self._load_state()

        if self.state['phase'] == 'DONE':
            # print('Done')
            return False

        msg = None
        inbox = read_inbox()
        write = False
        if inbox:
            write = True if inbox['msg_type'][0] == 'T' else False
            inbox['msg_type'] = inbox['msg_type'][1:]
        if self.state['phase'] == 'LOCK':
            if inbox and (inbox['msg_type'] == 'DONE' or inbox['msg_type'] == 'UNLO'):  # locked
                self.state['phase'] = 'UNLOCK'
            else:
                return True


        inbox_value = None
        if inbox:  # update infor
            inbox_value = inbox['values']

        nextindex = min(self.state['len'], self.state['index'] + 11)
        # check phase
        if self.state["phase"] == "INIT" and not inbox:  # if self is first
            msg = Message('UNLO', self.data[self.state['index']:nextindex])
            self.state['index'] = nextindex
            if nextindex >= self.state['len']:
                msg.msg_type = 'DONE'
                self.state['phase'] = 'DONE'
            else:
                self.state['phase'] = 'LOCK'
        elif inbox and inbox['msg_type'] == 'DONE':  # if other Done, output all and Done
            if self.state["phase"] == 'DONE':  # check if done
                pass
            else:  # output all till done
                for i in inbox_value:
                    self.state['phase'] = output_till(i, True)
                self.state['phase'] = output_till(self.data[-1] + 1)
                msg = Message('DONE', [])
                # print(self.state['phase'])
        else:  # not finished, not first, try output
            if inbox_value:
                for i in inbox_value:
                    self.state['phase'] = output_till(i, True)
                    # print(self.state['phase'])
            nextindex = min(self.state['len'], self.state['index'] + 11)
            msg = Message('UNLO', self.data[self.state['index']:nextindex])
            self.state['index'] = nextindex
            if self.state['phase'] != 'DONE':
                self.state['phase'] = 'LOCK'
            else:
                msg.msg_type = 'DONE'

        self._save_state()
        if write:
            msg.msg_type='T'+msg.msg_type
        else:
            msg.msg_type='F'+msg.msg_type

        if self.state['phase'] == 'DONE':
            write_msg(msg)
            return False

        write_msg(msg)

        if inbox and inbox['msg_type'] == self.state['phase'] == 'DONE':  # check if all Done
            return False
        return True

    def get_stats(self) -> WorkerStats:
        """Return statistics about work performed."""
        return self.stats
    
class Coordinator:
    def __init__(self, worker_a: MergeWorker, worker_b: MergeWorker):
        self.workers = [worker_a, worker_b]

    def run(self, max_steps: int = 10000) -> dict:
        """Alternate workers until both done or max steps reached."""
        steps = 0
        active = [True, True]

        while any(active) and steps < max_steps:
            for i, worker in enumerate(self.workers):
                if active[i]:
                    active[i] = worker.step()
                    steps += 1

        return {
            "success": not any(active),
            "total_steps": steps,
            "stats_a": self.workers[0].get_stats(),
            "stats_b": self.workers[1].get_stats()
        }
        
# def test(data1,data2):
#     inbox_a = Path("B_to_A.msg")
#     outbox_a = Path("A_to_B.msg")
#     state_a = Path("state_a.json")

#     inbox_b = Path("A_to_B.msg")
#     outbox_b = Path("B_to_A.msg")
#     state_b = Path("state_b.json")
#     output = Path("output.txt")
#     # outputa = Path("outputa.txt")
#     # outputb = Path("outputb.txt")


#     for path in [inbox_a, outbox_a, output, state_a,
#                  inbox_b, outbox_b, output, state_b]:
#         if path.exists():
#             path.unlink()

#     worker_a = MergeWorker("A", data1, inbox_a, outbox_a, output, state_a)
#     worker_b = MergeWorker("B", data2, inbox_b, outbox_b, output, state_b)

#     coordinator = Coordinator(worker_a, worker_b)
#     result = coordinator.run()

#     if output.exists():
#         with open(output) as f:
#             merged_output = [
#                 int(x)
#                 for line in f
#                 for x in line.split(',')
#                 if x.strip()
#             ]

#     expected = sorted(data1 + data2)

#     correct = (merged_output == expected)

#     print("Merged Output:", merged_output)
#     print("Expected     :", expected)
#     print("Correct     :", correct)
#     print("Coordinator Result:", result)
    
# if __name__ == "__main__":
            
#     # Test case: simple merge
#     data_a = list(range(0, 100, 2))    # Even numbers 0-98
#     data_b = list(range(1, 100, 2))    # Odd numbers 1-99
#     # Expected output: 0, 1, 2, 3, ..., 99
#     test(data_a, data_b)
#     # Test case: non-overlapping ranges
#     data_a = list(range(1000, 6000))   # 1000-5999
#     data_b = list(range(0, 1000))      # 0-999
#     # Expected output: 0, 1, 2, ..., 5999
#     test(data_a, data_b)

#     # Test case: interleaved ranges
#     data_a = [1, 5, 9, 13, 17, 21]
#     data_b = [2, 6, 10, 14, 18, 22]
#     # Expected output: 1, 2, 5, 6, 9, 10, 13, 14, 17, 18, 21, 22
#     test(data_a, data_b)

#     data_a = list(range(100, 600))   # 100-599
#     data_b = list(range(0, 100))      # 0-99
#     # Expected output: 0, 1, 2, ..., 5999
#     test(data_a, data_b)
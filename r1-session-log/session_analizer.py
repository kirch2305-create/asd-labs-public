import sys

class Stack:
    def __init__(self):
        self._top = None

    def push(self, x):
        self._top = (x, self._top)

    def pop(self):
        if self._top is None:
            raise IndexError("pop from empty stack")
        value = self._top[0]
        self._top = self._top[1]
        return value

    def top(self):
        if self._top is None:
            raise IndexError("top of empty stack")
        return self._top[0]

    def empty(self):
        return self._top is None

    def __iter__(self):
        node = self._top
        while node is not None:
            yield node[0]
            node = node[1]

def parse_event(raw_line, expected_tokens):
    line = raw_line.strip()
    if not line:
        return None
    tokens = line.split()
    if len(tokens) not in (2, 3):
        return None
    kind = tokens[0]
    if kind not in ("LOGIN", "LOGOUT"):
        return None
    name = tokens[1]

    if len(tokens) == 2:
        if expected_tokens == 3:
            return None
        return (kind, name, None, 2)

    if expected_tokens == 2:
        return None
    if not tokens[2].isdigit():
        return None
    return (kind, name, int(tokens[2]), 3)

class Analizer:
    def __init__(self, per_user=False, force_times=False):
        self.per_user = per_user
        if per_user:
            self.stacks = {}
        else:
            self.stack = Stack()

        self.expected_tokens = 3 if force_times else None

        self.sessions_closed = 0
        self.errors = []

        self.active = 0
        self.peak = 0
        self.peak_line = 0

        self.duration_sum = 0
        self.duration_count = 0

    def _handle_login(self, name, line_no, time_value):
        record = (name, line_no, time_value)
        if self.per_user:
            st = self.stacks.get(name)
            if st is None:
                st = Stack()
                self.stacks[name] = st
            st.push(record)
        else:
            self.stack.push(record)

        self.active += 1
        if self.active > self.peak:
            self.peak = self.active
            self.peak_line = line_no

    def _handle_logout(self, name, line_no, time_value):
        if self.per_user:
            st = self.stacks.get(name)
            if st is None or st.empty():
                self.errors.append((line_no, "logout_without_login"))
                return
            popped = st.pop()
        else:
            if self.stack.empty():
                self.errors.append((line_no, "logout_without_login"))
                return
            top_name = self.stack.top()[0]
            if top_name != name:
                self.errors.append((line_no, "order_violation"))
                return
            popped = self.stack.pop()

        self.sessions_closed += 1
        self.active -= 1

        _name, _line, open_time = popped
        if (self.expected_tokens == 3
                and open_time is not None
                and time_value is not None):
            self.duration_sum += time_value - open_time
            self.duration_count += 1

    def process_line(self, line, line_no):
        if line.strip() == "":
            return

        ev = parse_event(line, self.expected_tokens)
        if ev is None:
            self.errors.append((line_no, "bad_event"))
            return

        kind, name, time_value, tokens_count = ev

        if self.expected_tokens is None:
            self.expected_tokens = tokens_count
        elif tokens_count != self.expected_tokens:
            self.errors.append((line_no, "bad_event"))
            return

        if kind == "LOGIN":
            self._handle_login(name, line_no, time_value)
        else:
            self._handle_logout(name, line_no, time_value)

    def finalize(self):
        if self.per_user:
            opened = []
            for st in self.stacks.values():
                for item in st:
                    opened.append(item)
        else:
            opened = list(self.stack)

        opened.sort(key=lambda rec: rec[1])
        for _name, line_no, _t in opened:
            self.errors.append((line_no, "session_not_closed"))
        return self.errors

def main():
    args = sys.argv[1:]
    per_user = "--per-user" in args
    show_stats = "--stats" in args
    force_times = "--times" in args
    args = [a for a in args if a not in ("--per-user", "--stats", "--times")]

    if len(args) != 2:
        print("usage: session_analizer.py <input> <output> "
              "[--per-user] [--stats] [--times]")
        return

    in_path, out_path = args
    analizer = Analizer(per_user=per_user, force_times=force_times)

    with open(in_path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            analizer.process_line(line, line_no)

    analizer.finalize()

    with open(out_path, "w", encoding="utf-8") as f:
        for line_no, code in analizer.errors:
            f.write("ERROR {} {}\n".format(line_no, code))
        f.write("SESSIONS {}\n".format(analizer.sessions_closed))
        if show_stats and analizer.peak > 0:
            f.write("PEAK {} {}\n".format(analizer.peak, analizer.peak_line))
        if show_stats and analizer.duration_count > 0:
            avg = analizer.duration_sum / analizer.duration_count
            f.write("AVG_DURATION {}\n".format(avg))

if __name__ == "__main__":
    main()
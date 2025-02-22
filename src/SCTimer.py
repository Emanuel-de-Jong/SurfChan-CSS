import random
from time import perf_counter, sleep

class SCTimer():
    _times = {}

    def start(self, name):
        if not name in self._times:
            self._times[name] = {
                "current": 0,
                "times": []
            }
        
        self._times[name]["current"] = perf_counter()
    
    def stop(self, name):
        self._times[name]["times"].append(perf_counter() - self._times[name]["current"])

    def print(self):
        for name in self._times:
            self.print_name(name)

    def print_name(self, name):
        top_count = 5

        times = self._times[name]["times"]
        length = len(times)

        avg = sum(times) / length
        top_highest = sorted(times, reverse=True)[:top_count]

        output = f"{name}: {length} times, avg: {avg:.4f}s, {top_count} highest:"
        for time in top_highest:
            output += f" {time:.4f}s"

        print(output)

sc_timer = SCTimer()

if __name__ == "__main__":
    for i in range(10):
        sc_timer.start("test")
        sleep(random.randrange(1, 10) / 10.0)
        sc_timer.stop("test")
    sc_timer.print()

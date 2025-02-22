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
    
    def stop(self, name, should_print=False):
        if not name in self._times:
            return
        
        time = perf_counter() - self._times[name]["current"]
        self._times[name]["times"].append(time)
        self._times[name]["current"] = 0

        if should_print:
            print(f"{name}: {time:.4f}s")

    def clear(self, name):
        self._times[name]["times"] = []

    def print(self, name=None):
        if name:
            self._print_name(name)
        else:
            for name in self._times:
                self._print_name(name)

    def _print_name(self, name):
        top_count = 5

        if self._times[name]["current"] != 0:
            self.stop(name)

        times = self._times[name]["times"]
        treshold = sum(times) / len(times) * 100
        times = [time for time in times if time < treshold]

        count = len(times)
        avg = sum(times) / count
        total = int(sum(times))
        total_m = int(total / 60)
        total_h = int(total_m / 60)
        top_highest = sorted(times, reverse=True)[:top_count]

        output = f"{name}: count={count}, total={total}s|{total_m}m|{total_h}h, avg={avg:.4f}s, {top_count} highest="
        for time in top_highest:
            output += f"{time:.4f}s "

        print(output)

sc_timer = SCTimer()

if __name__ == "__main__":
    for i in range(10):
        sc_timer.start("test")
        sleep(random.randrange(1, 10) / 50.0)
        sc_timer.stop("test")
    sc_timer.print()

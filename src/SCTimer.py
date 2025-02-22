import random
from time import perf_counter, sleep

class SCTimer():
    _timers = {}

    def start(self, name):
        if not name in self._timers:
            self._timers[name] = {
                "current": 0,
                "times": []
            }
        
        self._timers[name]["current"] = perf_counter()
    
    def stop(self, name, should_print=False):
        if not name in self._timers:
            return
        
        time = perf_counter() - self._timers[name]["current"]
        self._timers[name]["times"].append(time)
        self._timers[name]["current"] = 0

        if should_print:
            print(f"{name}: {time:.4f}s")

    def clear(self, name):
        self._timers[name]["times"] = []

    def to_dict(self, category=None):
        timers = self._timers
        if category:
            timers = dict(filter(lambda item: item[0].startswith(category), self._timers.items()))
        
        timer_dict = {}
        for name, timer in timers.items():
            base_name = name.replace(category, "")
            timer_dict[base_name] = timer["times"][-1]
        
        return timer_dict

    def print(self, name=None):
        if name:
            self._print_name(name)
        else:
            sorted_timers = sorted(self._timers)
            for name in sorted_timers:
                self._print_name(name)

    def _print_name(self, name):
        top_count = 5

        if self._timers[name]["current"] != 0:
            self.stop(name)

        times = self._timers[name]["times"]
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
        sc_timer.start("ts:test")
        sleep(random.randrange(1, 10) / 50.0)
        sc_timer.stop("ts:test")

    print(sc_timer.to_dict("ts:"))

    sc_timer.print()

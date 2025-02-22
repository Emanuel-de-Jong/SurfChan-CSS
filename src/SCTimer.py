import random
from time import perf_counter, sleep

class SCTimer():
    _BASE_CATEGORY = "_base"
    _PRINT_TOP_HIGHEST_COUNT = 5
    _timers = {}

    def __init__(self):
        self._timers[self._BASE_CATEGORY] = {}

    def start(self, name, category=_BASE_CATEGORY):
        category_timers = self._timers.setdefault(category, {})
        timer = category_timers.setdefault(name, {"current": 0, "times": []})
        timer["current"] = perf_counter()
    
    def stop(self, name, category=_BASE_CATEGORY, should_print=False):
        if category not in self._timers or name not in self._timers[category]:
            return None
        
        timer = self._timers[category][name]
        elapsed_time = perf_counter() - timer["current"]
        timer["times"].append(elapsed_time)
        timer["current"] = 0

        if should_print:
            print(f"{name}: {elapsed_time:.4f}s")
        
        return elapsed_time
    
    def get_latest(self, name, category=_BASE_CATEGORY):
        if category not in self._timers or name not in self._timers[category]:
            return None
        
        return self._timers[category][name]["times"][-1]

    def clear(self, name, category=_BASE_CATEGORY):
        self._timers[category][name]["times"] = []

    def to_dict(self, category=None, prefix=None):
        if category is None:
            timers = {
                name: timer for timers in self._timers.values()
                for name, timer in timers.items()
            }
        else:
            timers = self._timers.get(category, {})

        return {
            (f"{prefix}{name}" if prefix else name): timer["times"][-1]
            for name, timer in timers.items()
        }

    def print(self, name=None, category=_BASE_CATEGORY):
        if name:
            print(self._name_to_str(name, category))
        else:
            sorted_categories = sorted(self._timers)
            for category_to_print in sorted_categories:
                if category_to_print != self._BASE_CATEGORY:
                    print(f"{category_to_print}:")
                
                sorted_timers = sorted(self._timers[category_to_print])
                for name_to_print in sorted_timers:
                    output = self._name_to_str(name_to_print, category_to_print)
                    if category_to_print != self._BASE_CATEGORY:
                        output = f"  {output}"
                    
                    print(output)

    def _name_to_str(self, name, category=_BASE_CATEGORY):
        if self._timers[category][name]["current"] != 0:
            self.stop(name, category)

        times = self._timers[category][name]["times"]
        treshold = sum(times) / len(times) * 100
        times = [time for time in times if time < treshold]

        count = len(times)
        avg = sum(times) / count
        total = int(sum(times))
        total_m = int(total / 60)
        total_h = int(total_m / 60)
        top_highest = sorted(times, reverse=True)[:self._PRINT_TOP_HIGHEST_COUNT]

        output = f"{name}: count={count}, total={total}s|{total_m}m|{total_h}h, avg={avg:.4f}s"
        output += f", {self._PRINT_TOP_HIGHEST_COUNT} highest="
        for time in top_highest:
            output += f"{time:.4f}s "

        return output

sc_timer = SCTimer()

if __name__ == "__main__":
    sc_timer.start("tot")
    for i in range(10):
        sc_timer.start("test", "ts")
        sleep(random.randrange(1, 10) / 50.0)
        sc_timer.stop("test", "ts")
    sc_timer.stop("tot")

    print(sc_timer.to_dict("ts", "tests/"))

    sc_timer.print()

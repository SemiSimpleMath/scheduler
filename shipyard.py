import sutils
import parameters

import itertools
import math

"""
Shipyard class
"""

print(f"{__name__} {parameters.VERSION}")

class Shipyard:
    def __init__(self, sy=None):

        self.tasks = []
        self.assigned = False  # This flags if the shipyard has definite action already for this turn
        self.conditional_time = None
        self.this_turn_action = None
        self.id = sy.id
        self.position = sy.position
        self.ship_count = sy.ship_count
        self.max_spawn = sy.max_spawn
        self.num_destroyed = 0
        self.counter = itertools.count()
        self.expanding = False
        self.turns_controlled = -1
        self.ideal_gather_amount = 8
        self.excess = 0
        self.last_assigned = None
        self.assign_path = []
        self.defending = False

        return

    def update(self, s, turn, board, me, enemy):
        self.ship_count = s.ship_count
        self.max_spawn = s.max_spawn
        self.conditional_time = None
        self.this_turn_action = None
        self.create_default_tasks(turn, board, me, enemy)
        self._turns_controlled = s._turns_controlled
        self.reserved_ships = []
        self.excess = self.ship_count
        self.last_assigned = None
        self.assign_path = []
        self.defending = False

    def create_default_tasks(self, turn, board, me, enemy):

        task = {"id": self.id, "type": "round_trip", "request_time": turn,
                "reserved": self.ideal_gather_amount,
                "reserve_type": 0, "priority": parameters.ROUND_TRIP_PRIORITY}
        self.push_task(task)

        spawn_priority = parameters.SPAWN_PRIORITY - self.max_spawn / 10
        # if me.kore > enemy.kore + 2000 and len(me.shipyards) > len(enemy.shipyards):
        #     spawn_priority -= 1
        if me.kore > 500 and self.ship_count < 80:
            spawn_priority -= .4
        task = {"id": self.id, "type": "spawn_max", "request_time": turn, "reserved": -1,
                "reserve_type": 0, "priority": spawn_priority}

        self.push_task(task)

        assert len(self.tasks) >= 2

    def delete_task(self, task_id):
        remove = -1
        for i, t in enumerate(self.tasks):
            if "task_id" in t and task_id == t["task_id"]:
                remove = i
        if remove >= 0:
            self.tasks.pop(remove)

        return

    def can_spawn(self, amount, steps):
        ms = self.compute_max_spawn(steps)
        if ms <= amount:
            return True

        return False

    def reserved_by_higher_priority(self, priority):
        reserved = 0
        for t in self.tasks:
            p = t["priority"]
            if p < priority:
                if "reserved" in t:
                    reserved += t["reserved"]
        return reserved

    def compute_available(self, sm, s, task):
        DEBUG = False
        if DEBUG and self.defending and task["type"]=="round_trip":
            debug = 1
        fleets = sm.me.fleets

        request_time = task["request_time"]
        priority = task["priority"]

        higher_priority_tasks = self.get_higher_priority_tasks(priority)
        if len(higher_priority_tasks) == 0:
            return

        highest_priority_request_time = self.get_conditional_time(priority)


        # first approximation:
        # 1) Get highest priority event and the request time
        # 2) Get number of returning + number can spawn + ship_count at request time = FUTURE TOTAL
        # 3) Get amount of time from now to then
        # 4) If this time is negative. Meaning this lower priority event is actually
        #    further in the future, just skip it.
        # Otherwise, compute FUTURE TOTAL - TOTAL NOW This is the excess
        # If the excess is negative we will spawn.

        # ccnditional time is the time from now to the nearest higher priority reserved.

        higher_reserved = sum([t["reserved"] for t in higher_priority_tasks])

        if DEBUG and self.defending and task["type"]=="round_trip":
            print(f"------{sm.board.step}------{s.position}")
            print(f"This task that is being considered: {task['type']}, priority {task['priority']}")

        num_returning2 = sutils.number_of_returning_ships(sm.board, fleets, self.position,
                                                          highest_priority_request_time - sm.board.step)
        num_returning1 = sutils.number_of_returning_ships(sm.board, fleets, self.position, request_time - sm.board.step)

        time_diff = highest_priority_request_time - request_time

        # You have to subtract one turn from spawn amount to compute correct excess.
        # Otherwise, if a fleet is sent out it takes up one spawn turn so there is one spawn less
        # of excess

        spawn_amount = sutils.amount_ships_can_spawn_in_n_steps(sm.board, time_diff - 1, s, sm.me.kore)
        self.excess = s.ship_count + spawn_amount + num_returning2 - num_returning1 - higher_reserved  # highest_priority_task["reserved"]
        self.excess = min(s.excess, s.ship_count)
        # let's just use the closest upcoming higher priorities conditional time
        self.conditional_time = self.get_conditional_time(priority)
        if DEBUG and self.defending:
            print(sm.board.step, s.position, s.ship_count, spawn_amount, num_returning2, num_returning1, higher_reserved )

            print(self.excess)
            print(self.conditional_time)

        return False

    def push_task(self, task):

        priority = task["priority"]
        request_time = task["request_time"]
        type = task["type"]

        for ta in self.tasks:
            if priority == ta["priority"] and request_time == ta["request_time"] and type == ta["type"]:
                #print("Error, duplicate task being pushed.")
                return False
        self.tasks.append(task)
        return True

    def get_highest_priority_task(self):
        mp = 0
        highest = None
        for t in self.tasks:
            p = t["priority"]
            if p < mp:
                highest = t
                mp = p
        return highest

    def get_higher_priority_tasks(self, priority):
        tasks = []
        for t in self.tasks:
            p = t["priority"]
            if priority > p:
                tasks.append(t)
        return tasks



    def get_conditional_time(self, pr):
        ct = 999
        for task in self.tasks:
            p = task["priority"]
            if p < pr:
                time = task["request_time"]
                if time < ct:
                    ct = time
        if ct == 999:
            return None
        else:
            return ct

    def is_expanding(self):
        for t in self.tasks:
            if t["type"] == "expand":
                return True
        return False

    def compute_max_spawn(self, steps):
        spawns = 0
        if steps == 0:
            return 0
        turns_controlled = self.turns_controlled
        for i in steps:
            spawns += int(math.sqrt(turns_controlled + i - 1) + 1)
        return spawns

    def get_conditional(self):
        conditional_time = None
        if self.conditional_time is not None:
            conditional_time = min(self.conditional_time, 400)
        return conditional_time

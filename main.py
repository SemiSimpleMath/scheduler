import shipyardmanager
import parameters
import fleet_info
import sutils

import copy
import heapq as hq
import itertools

import kaggle_environments.envs.kore_fleets.helpers as kf


print(f"{__name__} {parameters.VERSION}")

DEBUG = False
class Agent:
    def __init__(self):
        self.status = {}
        self.board = None
        self.config = None
        self.scheduler = None
        return

    @property
    def me(self):
        return self.board.current_player

    @property
    def kore(self):
        return self.me.kore

    def generate_actions(self, board, config):
        self.board = board
        self.config = config
        self.scheduler.update(board, config)
        return self.scheduler.get_actions(board)


    @staticmethod
    def is_expanding(board):
        fleets = board.current_player.fleets
        for f in fleets:
            if "C" in f.flight_plan:
                return True
        return False


class Scheduler:
    def __init__(self, board=None, config=None):
        self.board = copy.deepcopy(board)
        self.config = config
        self.sm = shipyardmanager.ShipyardManager()
        self.counter = itertools.count()
        self.priorities = []
        self.fi = fleet_info.FleetInfo()

    def update(self, board, config):
        self.board = copy.deepcopy(board)
        self.config = copy.deepcopy(config)
        self.sm.update(self.board, self.config)
        self.fi.update(self.board)
        sutils.cache.update(self.board)

    def resolve_scheduled_events(self):

        while len(self.priorities) > 0:

            p, count, task = hq.heappop(self.priorities)

            s_id = task["id"]
            s = self.sm.get_shipyard_by_id(s_id)
            if s is None:
                assert 1 == 0 , f"{task['type']}"
                continue
            if s.assigned:
                continue
            s.assign_path.append(f"task: {task['type']}")
            if DEBUG:
                print(f"{self.board.step}: {s.position}, type {task['type']}, priority {task['priority']} reserved ,{task['reserved']}")
            # update s.excess
            s.compute_available(self.sm, s, task)

            time_until_task = task["request_time"] - self.board.step

            if time_until_task == 0:
                self.assign_action(s, task)
            elif task["type"] == "spawn_max_defense":
                self.assign_action(s, task)
            else:
                s.assign_path.append(f"{task['type']} not ready yet.")



    def assign_action(self, s, task):


        if task["type"] == "round_trip":
            s.assign_path.append("Trying round trip")
            return self.sm.assign_return_route(self.board, s)

        if task["type"] == "spawn_max":
            s.assign_path.append("Trying spawn max")
            return self.sm.spawn_max(s)

        if task["type"] == "expand":
            s.assign_path.append("Trying expand")
            return self.sm.assign_expand(s)

        if task["type"] == "defend":
            s.assign_path.append("Trying defend")
            return self.sm.assign_defend(s, task)

        if task["type"] == "spawn_max_defense":
            s.assign_path.append("Trying to spawn_max_defense")
            if s.ship_count < task["reserved"]:
                return self.sm.spawn_max(s)
            s.assign_path.append("spawn_max_defense already reached the spawn goal")
            return False

        if task["type"] == "snipe":
            s.assign_path.append("Trying to snipe")
            location = task["location"]
            path = sutils.get_snipe_path(s.position, location)
            amount = task["reserved"]
            if amount > s.excess:
                return False
            s.assign_path.append("snipe in main")
            return self.sm.launch(s, path, amount)


        if task["type"] == "attack_shipyard":
            s.assign_path.append("Trying to attack shipyard")
            return self.sm.attack_shipyard(s, task)

        if task["type"] == "abandon":
            return self.sm.abandon(s)


        return

    def update_task_queue(self):
        for s in self.sm.shipyards:
            if s.defending:
                debug = 1
            temp = []
            assert len(s.tasks) >= 2
            counter = 0
            while len(s.tasks) > 0:
                task = s.tasks.pop(0)
                p = task["priority"]
                if task["request_time"] >= self.board.step + 50:
                    print("VERY STRANGE REQUEST TIME")
                    print(f"{s.assign_path}")
                    continue
                if task["request_time"] >= self.board.step:
                    hq.heappush(self.priorities, (p, next(self.counter), task))
                    counter += 1
                if task["request_time"] > self.board.step:
                    temp.append(task)
            assert counter >= 2
            s.tasks = temp

    def get_actions(self, board):
        global predictions
        global actual
        self.assign_priority_tasks()
        self.update_task_queue()
        self.resolve_scheduled_events()
        actions = self.get_shipyard_actions(self.sm)
        me = board.current_player
        for s_id, action in actions.items():
            for sy in me.shipyards:
                if sy.id == s_id:
                    sy.next_action = action


        DEBUG = False
        if DEBUG:
            print(f"+++++++++++++++ Actions for step: {self.board.step} ++++++++++++++++++++++++++")
            for s_id, action in actions.items():
                for sy in self.sm.shipyards:
                    if sy.id == s_id and sy.assigned is False:
                        print(f"{sy.ship_count}, {sy.position} is s assigned {action} {sy.assigned}, {sy.assign_path}")
                        if not sy.assigned:
                            print("ASSIGN PATH", sy.assign_path)
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

        # if board.step == 90:
        #     for i in range(1, 11):
        #         predictions.append(sutils.amount_of_kore_returning_in_n_steps(board, board.current_player, i))
        # if 90 < board.step < 102:
        #     actual[board.step] = {}
        #     actual[board.step]["start"]=me.kore
        #     actual[board.step]["spent"]=self.km.amount_spent_this_turn
        #     actual[board.step]["end"] = me.kore + self.km.amount_spent_this_turn
        #     if board.step - 1 in actual:
        #         actual[board.step]["gain"] = actual[board.step]["start"] - actual[board.step-1]["end"]
        #
        #
        # if len(actual) == 10:
        #     print(predictions)
        #     unit_tests.test_amount_of_kore_in_n_turns(predictions, actual)

        return me.next_actions

    def assign_priority_tasks(self):

        self.sm.assign_defenders(self.fi, self.board)
        self.sm.assign_short_distance_attackers()
        self.sm.assign_avalanche_attackers()
        self.sm.assign_expanders()
        self.sm.assign_unstoppable_attack()
        self.sm.assign_attack()
        #self.sm.assign_reinforce()
        #self.sm.assign_snipe()



        return

    @staticmethod
    def get_shipyard_actions(sm):
        action_dict = {}
        for s in sm.shipyards:
            action_dict[s.id] = s.this_turn_action
        return action_dict

player = Agent()
player.scheduler = Scheduler()
predictions = []
actual = {}
def agent(obs, config):
    global player
    global cache
    board = kf.Board(obs, config)
    if player is None:
        player = Agent()
        player.scheduler = Scheduler()

    return player.generate_actions(board, config)

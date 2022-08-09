import fleet_info
import sutils
import shipyard
import parameters

import copy
from typing import List, Union, Dict

import math
import logging
import kaggle_environments.envs.kore_fleets.helpers as kf
import timeit
import fleet_info

DEBUG = False
print(f"{__name__} {parameters.VERSION}")
# if '__file__' in globals():
#     logger = logging.getLogger(__file__)
# else:
#     logger = logging.getLogger('shipyardmanager.py')
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='{asctime} {name} {levelname:8s} {message}',
#     style='{',
#     handlers=[
#         #logging.FileHandler("debug.log"),
#         #logging.StreamHandler(sys.stdout)
#     ]
# )
#
# sh = logging.StreamHandler(sys.stdout)
# sh.setLevel(logging.DEBUG)
# logger.addHandler(sh)
#
# if os.path.exists("C:/Users/semis/IdeaProjects/kaggle-kore-2022/scheduler_logs"): now = datetime.datetime.now() fh
# = logging.FileHandler("C:/Users/semis/IdeaProjects/kaggle-kore-2022/scheduler_logs/scheduler" + now.strftime(
# "%d-%m-%Y-%H-%M-%S") + ".log", mode='a') fh.setLevel(logging.DEBUG) logger.addHandler(fh)

DEFENSE_LOGGING = False
ATTACK_LOGGING = False
EXPO_LOGGING = False
CONDITIONAL_LOGGING = False
ROUND_TRIP_DEBUG = False


# ==============================  ShipyardManager =============================

def is_defending(s: shipyard.Shipyard) -> bool:
    for t in s.tasks:
        if t["type"] == "defending" or t["type"] == "spawn_max_defense":
            return True
    return False


def num_fleets_expanding(fleets: List[kf.Fleet]) -> int:
    count = 0
    for f in fleets:
        if "C" in f.flight_plan:
            count += 1
    return count


def is_attacking(s):
    for t in s.tasks:
        if t["type"] == "attack_shipyard":
            return True
    return False


class ShipyardManager:
    def __init__(self, board=None, config=None):
        if board is not None:
            self.me = board.current_player
        else:
            self.me = None
        self.board = copy.deepcopy(board)
        self.config = config
        self.shipyards = []
        self.pending_expansions = 0
        self.intended_expos = {}
        self.true_expos = []
        self.kore = 0

        return

    def add(self, s: shipyard.Shipyard) -> None:
        self.shipyards.append(s)

    def update(self, board, config):
        # update the shipyards with new shipyards if they are not in the list

        self.board = board
        self.config = config
        self.me = self.board.current_player
        self.kore = self.me.kore
        my_shipyard_ids = [s.id for s in self.shipyards]
        my_board_shipyards = board.players[self.me.id].shipyards
        my_board_shipyard_ids = [s.id for s in my_board_shipyards]
        # go through board shipyards
        for s in my_board_shipyards:
            if s.id not in my_shipyard_ids:
                sy = shipyard.Shipyard(s)
                self.add(sy)

        # remove shipyards that no longer exist
        # go through my shipyards
        remove = []
        for i, s in enumerate(self.shipyards):
            if s.id not in my_board_shipyard_ids:
                remove.append(s.id)
        for r in remove:
            for i, s in enumerate(self.shipyards):
                if r == s.id:
                    self.shipyards.pop(i)
                    break

        # finally we agree which shipyards are in the game.
        # let's update each one of our shipyard objectsF

        for i, s in enumerate(self.shipyards):
            self.shipyards[i].update(self.board.shipyards[s.id], self.board.step, self.board, self.board.current_player,
                                     self.get_enemy())

        for s in self.shipyards:
            s.assigned = False
            s.conditional_time = None

        self.true_expos = []
        for s in self.shipyards:
            if s.position in self.intended_expos:
                self.true_expos.append(s.position)

    def get_unassigned_shipyards(self) -> List[shipyard.Shipyard]:
        result = []
        for s in self.shipyards:
            if not s.assigned:
                result.append(s)
        return result

    def get_enemy(self) -> kf.Player:
        me = self.me
        enemy = None
        for s_id, p in self.board.players.items():
            if p == me:
                continue
            else:
                enemy = p
        return enemy

    def excess_vs_conditional(self, board: kf.Board, s: shipyard.Shipyard) -> bool:

        my_shipyards = self.shipyards
        enemy_shipyards = self.get_enemy().shipyards
        enemy_fleets = self.get_enemy().fleets
        my_fleets = self.me.fleets

        ships_min = 8
        ships_max = 999

        if len(self.shipyards) >= 15:
            max_length = 36
        else:
            max_length = 40

        #This is the key.  The longest available path is capped by conditional time

        if s.excess < s.ship_count and s.excess < 34:

            max_l = min(s.get_conditional() - board.step, max_length)
            if CONDITIONAL_LOGGING:
                print(f"{self.board.step} {s.position} Conditional time is {s.conditional_time} max_l is: {max_l}")

            if s.ship_count < 8:
                s.assign_path.append("ship_count < 8")
                return False
            if s.excess >= 8 and max_l >= 2:

                ranked_paths1 = sutils.generate_return_path_with_most_kore(board, s, my_shipyards, s.position,
                                                                           max_length)

                fp1, best_size1, expected_kore1 = sutils.find_best_path(ranked_paths1, s.excess, ships_min, ships_max,
                                                                        self.board, my_fleets,
                                                                        enemy_fleets, my_shipyards, enemy_shipyards)

                ranked_paths2 = sutils.generate_return_path_with_most_kore(board, s, my_shipyards, s.position, max_l)

                fp2, best_size2, expected_kore2 = sutils.find_best_path(ranked_paths2, s.ship_count, ships_min,
                                                                        ships_max,
                                                                        self.board, my_fleets,
                                                                        enemy_fleets, my_shipyards, enemy_shipyards,
                                                                        True)

                if expected_kore1 <= expected_kore2:
                    fp, best_size = fp1, best_size1

                    if CONDITIONAL_LOGGING:
                        print(f"{self.board.step} Excess is better excess {s.excess}, best_size {best_size}")
                    if best_size > s.excess:
                        s.assign_path.append("Best size is bigger than s.excess")
                        return False

                else:
                    fp, best_size = fp2, best_size2
                    if CONDITIONAL_LOGGING:
                        print(f"{self.board.step} conditional is better")

                if fp is None:
                    s.assign_path.append("no fp after excess vs conditional")
                    return False

                s.assign_path.append("round trip excess vs cond time")
                return self.launch(s, fp.get_compact_path(), best_size)

            elif s.excess < 8 and max_l >= 2:
                max_l = min(s.get_conditional() - board.step, max_length)
                ranked_paths = sutils.generate_return_path_with_most_kore(board, s, my_shipyards, s.position, max_l)
                fp, best_size, expected_kore = sutils.find_best_path(ranked_paths, s.ship_count, ships_min, ships_max,
                                                                     self.board, my_fleets,
                                                                     enemy_fleets, my_shipyards, enemy_shipyards, True)

                if fp is None:
                    if CONDITIONAL_LOGGING:
                        print(f"{self.board.step} {s.position} Conditional path does not exist {max_l}")
                    s.assign_path.append("no fp after conditional")
                    return False
                if CONDITIONAL_LOGGING:
                    print(
                        f"{self.board.step} {s.position} Found a conditional path: best_size: {best_size},"
                        f" {s.ship_count} {fp.get_compact_path()} {max_l}")
                if best_size > s.ship_count:
                    s.assign_path.append("best_size > ship count at conditional")
                    return False

                s.assign_path.append("round trip cond time")
                return self.launch(s, fp.get_compact_path(), best_size)

            elif s.excess >= 8 and max_l < 2:
                ranked_paths1 = sutils.generate_return_path_with_most_kore(board, s, my_shipyards, s.position,
                                                                           max_length)
                fp, best_size, expected_kore = sutils.find_best_path(ranked_paths1, s.excess, ships_min, s.excess,
                                                                     self.board, my_fleets,
                                                                     enemy_fleets, my_shipyards, enemy_shipyards)
                if best_size > s.excess:
                    return False
                if fp is None:
                    s.assign_path.append("no fp for excess >= 8")
                    return False
                # print("got round trip", best_size, fp.get_compact_path())

                s.assign_path.append("round trip excess")
                return self.launch(s, fp.get_compact_path(), best_size)

            else:
                s.assign_path.append(f"Both excess and conditional too small{s.excess}, {max_l}")
                return False  # excess < 8 and max_l < 4

        ###############################################################################################################

    def yoyo_out_of_kore(self, s: shipyard.Shipyard) -> bool:
        amount = s.excess
        if amount < 8 and self.me.kore > 10:
            s.assign_path.append("amount < 8 kore > 10")
            return False
        elif (0 < amount < 8) and (self.me.kore < 10) and len(self.me.fleets) == 0:
            fp = "N"
            amount = min(amount, s.ship_count)
            s.assign_path.append('Round trip at nothing left despro yoyo')

            return self.launch(s, fp, amount)

            # todo implement best plan
        elif amount < 8:
            s.assign_path.append("amount < 8")
            return False

    def assign_return_route(self, board: kf.Board, s: shipyard.Shipyard) -> bool:

        assert s.excess <= s.ship_count

        round_trip_debug = [s.ship_count, s.excess]

        # if self.is_defending(s):
        # if DEFENSE_LOGGING:
        #  logger.debug(f"Step: {board.step} shipyard is defending, but considering sending for return route")
        #  logger.debug(f"excess is {s.excess}, conditional time is {s.get_conditional()}")

        my_shipyards = self.shipyards
        enemy_shipyards = self.get_enemy().shipyards
        enemy_fleets = self.get_enemy().fleets
        my_fleets = self.me.fleets

        ships_min = 8
        ships_max = 999

        if len(self.shipyards) >= 15:
            max_length = 36  #
        else:
            max_length = 40  # This is basically the chads radius 15.

        if s.ship_count < 8 and self.me.kore > 10:
            return False

        if s.conditional_time is not None or (s.excess < s.ship_count):
            self.excess_vs_conditional(board, s)

        amount = s.excess

        if s.ship_count < 8:
            self.yoyo_out_of_kore(s)

        if amount < 8:
            return False

        # ====================================================================================================
        # We are here the amount is now >= 8

        ranked_paths = sutils.generate_return_path_with_most_kore(board, s, my_shipyards, s.position, max_length)
        ranked_paths_copy1 = ranked_paths.copy()
        # ranked_paths_copy2 = ranked_paths.copy()
        #
        # print("**********scheduler************")
        # for i in range(0,10):
        #     index, r, best_size, fp = hq.heappop(ranked_paths_copy2)
        #     print(f"{self.board.step} {index}, {best_size}, {fp.get_compact_path()}")
        # print("******************************")

        fp, best_size, expected_kore = sutils.find_best_path(ranked_paths, s.excess, ships_min, ships_max,
                                                             self.board, my_fleets,
                                                             enemy_fleets, my_shipyards, enemy_shipyards)

        round_trip_debug.append(">= 8")
        round_trip_debug.append(best_size)

        if best_size > amount:
            # 1) Figure out if it makes sense to wait for more.
            # if enough ships are coming in soon. Either by spawning or just arriving
            wait_steps = parameters.WAIT_STEPS
            if sutils.max_amount_of_ships_in_n_steps(self.board, wait_steps, s, my_fleets, self.me.kore) >= best_size:
                s.assign_path.append("Best size is greater than amount but we can wait")
                return False

            # 2) It does not make sense to wait.  Just send out the most you can.

            ships_min = 8
            ships_max = amount

            if amount >= 34:
                ships_min = 34
            elif amount >= 21:
                ships_min = 21
            elif amount >= 13:
                ships_min = 13

            # using original ranked_paths here

            fp, best_size, kore = sutils.find_best_path(ranked_paths_copy1, amount, ships_min, ships_max,
                                                        self.board, my_fleets, enemy_fleets, my_shipyards,
                                                        enemy_shipyards, True)

            if best_size == 8 and self.me.kore > self.get_enemy().kore + 500:
                return False

            #### remove this soon ###
            best_size = min(best_size, amount)
            assert best_size <= amount, f"{best_size}, {amount}"

            round_trip_debug.append("Dont wait for more")
            round_trip_debug.append(best_size)

            if fp is None:
                s.assign_path.append("no fp here")
                return False

            s.assign_path.append('Round trip dont wait')
            assert best_size <= s.ship_count, f"{self.board.step}, {best_size}, {s.ship_count}, {s.excess}"
            return self.launch(s, fp.get_compact_path(), best_size)

        else:

            s.assign_path.append("round trip best_size <= amount")

            # We have more than best_size and can send bigger fleet if we wish
            enemy_fleet_top_median = sutils.get_fleet_top_median(self.get_enemy().fleets, 10)

            my_fleet_top_median = sutils.get_fleet_top_median(my_fleets, 10)

            # Here we can start to grow our fleet sizes.

            if board.step > 150 and len(my_fleets) >= 8 and len(self.get_enemy().fleets) > 8:

                greedy_size = int(1.1 * enemy_fleet_top_median) + 1

                best_size = min(max(best_size, greedy_size), s.ship_count)

                if board.step > 200 and amount < greedy_size and len(my_fleets) > 8:
                    return False
            #
            # if board.step > 150 and best_size == 8 and len(my_fleets) > 8:
            #     return False

            if fp is None:
                s.assign_path.append("no fp again?")
                return False

            fp = fp.get_compact_path()

            if best_size <= amount:
                best_size = min(best_size, amount, s.ship_count)
            if best_size < 8:
                s.assign_path.append("somehow yet again best_size < 8")
                return False
            if best_size > 34:
                # print(round_trip_debug)
                if DEBUG:
                    print(f"LAUNCHING ROUND TRIP {board.step}, {best_size}, {s.get_conditional()} {s.excess}")
            s.assign_path.append('Roundtrip the most common launch')

            return self.launch(s, fp, best_size)

    def find_expo_location(self, pos: kf.Point) -> kf.Point:
        start = pos
        radius = 6
        min_x, min_y = -radius, -radius
        max_x, max_y = radius, radius
        candidate_pt = None
        for i in range(min_x, max_x + 1):
            for j in range(min_y, max_y + 1):
                if abs(i) + abs(j) > radius:
                    continue
                if i == 0 and j == 0:
                    continue
                candidate_pt = kf.Point(i + start[0], j + start[1])

                if len(sutils.find_nearby_shipyards(self.board, candidate_pt, 5)) == 0:
                    if len(sutils.find_nearby_player_shipyards(self.board, candidate_pt, 6,
                                                               self.get_enemy().shipyards)) == 0:
                        return candidate_pt

        return candidate_pt

    def find_best_position_for_shipyards(self) -> Union[kf.Point, None]:

        scores = []
        for p in self.board.cells:
            if self.board.cells.get(p).kore > 50:
                continue

            closest_ship_yards = sutils.find_nearby_shipyards(self.board, p, parameters.FURTHEST_SHIPYARD)
            if len(closest_ship_yards) == 0:
                continue

            found_too_close = False
            for s in closest_ship_yards:
                if sutils.manhattan_distance(self.board, s.position, p) < parameters.CLOSEST_SHIPYARD:
                    found_too_close = True
            if found_too_close:
                continue

            enemy_num = 0
            enemy_spawn = 0
            my_num = 0
            my_spawn = 0

            enemy_min_dist = self.board.configuration.size
            my_min_dist = self.board.configuration.size
            ave_enemy_dist = 0
            ave_my_dist = 0
            for s in closest_ship_yards:
                dist = sutils.manhattan_distance(self.board, p, s.position)
                if s.id not in self.me.shipyard_ids:
                    enemy_num += 1
                    enemy_spawn += s.max_spawn
                    if dist < enemy_min_dist:
                        enemy_min_dist = dist
                    ave_enemy_dist += dist
                else:
                    my_num += 1
                    my_spawn += s.max_spawn
                    if dist < my_min_dist:
                        my_min_dist = dist
                    ave_my_dist += dist

            if enemy_min_dist < 8:
                continue

            if my_num == 0:
                continue

            # if len(self.shipyards) >= 3 and my_num < 2:
            #     continue

            if enemy_num > 0:
                if enemy_num >= my_num or my_min_dist >= enemy_min_dist:
                    continue

                ave_enemy_dist = ave_enemy_dist / enemy_num

                ave_my_dist = ave_my_dist / my_num

                if ave_my_dist > ave_enemy_dist:
                    continue

            nearby_kore = sum(
                self.board.cells.get(x).kore for x in sutils.find_all_pts_within_radius(self.board, p, r=10))

            scores.append((nearby_kore, p))

        scores = sorted(scores, key=lambda x: x[0])

        if len(scores) == 0:
            return None

        k, pt = scores[-1]

        return pt

    def get_shipyards_total_ship_count(self, s: shipyard.Shipyard) -> int:
        s_count = 0
        s_count += s.ship_count
        s_count += sutils.number_of_returning_ships(self.board, self.me.fleets, s.position, 400)
        return s_count

    def find_weakest_shipyard(self) -> Union[shipyard.Shipyard, None]:
        scores = []
        for s in self.shipyards:
            if s.position in self.true_expos:
                # score by max_spawn but also by total_ship_count
                # if total_ship_count is big then it should overpower the max_spawn
                scores.append((s.max_spawn, s))
        scores = sorted(scores, key=lambda x: x[0])
        if len(scores) > 0:
            return scores[0][1]
        else:
            return None

    def assign_reinforce(self):
        if len(self.shipyards) < 4:  # expriment with this number and make it into a parameter
            return
        # if self.me.kore < self.get_enemy().kore:
        #     return
        for s in self.shipyards:
            if s.ship_count > 50:  # make this number into a parameter
                target = self.find_weakest_shipyard()
                if target is None:
                    continue

                if target.max_spawn < s.max_spawn:
                    task = {"type": "defend", "request_time": self.board.step, "reserved": .5 * s.ship_count,
                            "location": target.position, "reserve_type": 1, "priority": parameters.REINFORCE_PRIORITY,
                            "id": s.id}
                    print(f"{self.board.step} Pushing reinforce")
                    s.push_task(task)
                    return True
        return False

    def assign_short_distance_attackers(self):
        enemy = self.get_enemy()
        used_ship_yards = {}
        for s in self.shipyards:
            if s.id in used_ship_yards:
                continue
            possible_attackers = [s]
            count = 0
            for e in enemy.shipyards:
                if sutils.manhattan_distance(self.board, s.position, e.position) < 6:
                    count += s.ship_count
                    for o in self.shipyards:
                        if o == s:
                            continue
                        if o in used_ship_yards:
                            continue
                        distance = sutils.manhattan_distance(self.board, o.position, e.position)
                        if distance < 7:
                            count += o.ship_count
                            possible_attackers.append(o)
                        else:
                            continue
                if count > e.ship_count:
                    if s.ship_count > e.ship_count:
                        for sy in possible_attackers:
                            used_ship_yards[sy.id] = sy.id
                            task = {"type": "attack_shipyard", "request_time": self.board.step + 2,
                                    "reserved": sy.ship_count + 20,
                                    "location": e.position,
                                    "reserve_type": 1, "priority": parameters.SHORT_DISTANCE_ATTACK_PRIORITY,
                                    "id": sy.id}
                            sy.push_task(task)

    def should_avalanche_attack(self):

        me_s = self.shipyards
        me_f = self.me.fleets
        enemy_s = self.get_enemy().shipyards
        enemy_f = self.get_enemy().fleets

        my_ships = sutils.get_total_ships(me_f, me_s)
        enemy_ships = sutils.get_total_ships(enemy_f, enemy_s)

        if my_ships > 2 * enemy_ships and my_ships > 300:
            return True
        else:
            return False

    def find_available_shipyards(self, priority):
        available = []
        for s in self.shipyards:
            high_priority = False
            for t in s.tasks:
                p = t["priority"]
                if p < priority:
                    high_priority = True
                    break
            if not high_priority:
                available.append(s)

        return available

    def assign_avalanche_attackers(self):

        if not self.should_avalanche_attack():
            return

        # find all available shipyards
        available = self.find_available_shipyards(-6)

        if len(available) == 0:
            return

            # select target
        target = None
        enemy = self.get_enemy()

        if len(enemy.shipyards) == 0:
            return

        if len(available) < 3:
            return

        first = available[0]
        target = self.score_enemy_targets(first)
        if target is None:
            return
        target = target.position
        longest = 0
        for s in available:
            d = sutils.manhattan_distance(self.board, s.position, target)
            if d > longest:
                longest = d

        for s in available:
            dist = sutils.manhattan_distance(self.board, s.position, target)
            send_time = longest - dist + 5
            most_can_get = sutils.max_amount_of_ships_in_n_steps(self.board, send_time, s, self.me.fleets, self.me.kore)
            if most_can_get < 21:
                continue
            task = {"type": "attack_shipyard", "request_time": self.board.step + send_time, "reserved": 100,
                    "location": target, "debug": "avalanche",
                    "reserve_type": 1, "priority": parameters.AVALANCHE_ATTACK_PRIORITY, "id": s.id}
            s.push_task(task)
            if ATTACK_LOGGING:
                print(f"{self.board.step} Pushing avalanche attack")

    def snipe_nearby_fleet(self, s):
        enemy = self.get_enemy()
        search_radius = 10
        if len(enemy.fleets) < 15:
            search_radius = 15

        f, target, size = sutils.closest_approach_fleet(self.board, s.position, enemy.fleets, search_radius)
        if f is None:
            return False, None, None, None
        steps = sutils.steps_for_fleet_to_reach_pt(self.board, f, target)

        if steps < sutils.manhattan_distance(self.board, target, s.position):
            return False, None, None, None

        wait_time = steps - sutils.manhattan_distance(self.board, target, s.position)

        return f, target, size, wait_time

    def score_enemy_targets(self, s):
        enemy = self.get_enemy()

        scores = []

        for e in enemy.shipyards:
            score = 0

            dist = sutils.manhattan_distance(self.board, s.position, e.position)

            num_defending = sutils.number_of_returning_ships(self.board, enemy.fleets, e.position, dist) + e.ship_count
            spawn_amount = e.max_spawn * dist

            if num_defending + spawn_amount > s.excess:
                continue

            cm = sutils.get_center_mass_player(enemy)

            dist_cm = sutils.manhattan_distance(self.board, e.position, kf.Point(cm[0], cm[1]))

            score = -dist + dist_cm - spawn_amount - 10 * (num_defending - s.ship_count)

            scores.append((score, e))

        if len(scores) == 0:
            return None

        scores.sort(key=lambda tup: tup[0])

        target = scores[-1][1]

        return target

    def should_attack(self, s):
        if is_attacking(s):
            return False
        if s.excess < 50:
            return False
        num_ships = sutils.get_total_ships(self.shipyards, self.me.fleets)
        num_enemy_ships = sutils.get_total_ships(self.get_enemy().shipyards, self.get_enemy().fleets)
        if num_enemy_ships == 0:
            return True
        # cargo condition:
        cargo_me = sutils.kore_in_cargo(self.me.fleets)
        cargo_enemy = sutils.kore_in_cargo(self.get_enemy().fleets)
        if num_ships / num_enemy_ships >= .8 and num_ships > 300 or (
                num_ships > 250 and cargo_me > cargo_enemy):
            return True
        return False

        # num_ships = sutils.get_total_ships(self.me.shipyards, self.me.fleets)
        # num_enemy_ships = sutils.get_total_ships(self.get_enemy().shipyards, self.get_enemy().fleets)
        # if num_enemy_ships == 0: return True
        # # cargo condition:
        # cargo_me = sutils.kore_in_cargo(self.me.fleets)
        # cargo_enemy = sutils.kore_in_cargo(self.get_enemy().fleets)
        # if num_ships / num_enemy_ships >= .8 and num_ships > 300 or (
        #         num_ships > 250 and cargo_me > cargo_enemy):
        #     return True
        # return False

    def assign_attack(self):
        for s in self.shipyards:
            if not self.should_attack(s):
                s.assign_path.append("at assign_attack. should not attack")
                continue
            enemy = self.get_enemy()
            target = self.score_enemy_targets(s)
            if target is not None:
                steps = sutils.manhattan_distance(self.board, s.position, target.position)
                defense = sutils.max_amount_of_ships_in_n_steps(self.board, steps, target, self.get_enemy().fleets,
                                                                self.get_enemy().kore)
                my_ships = sutils.get_total_ships(self.shipyards, self.me.fleets)

                enemy_ships = sutils.get_total_ships(enemy.shipyards, enemy.fleets)

                # # probe_prob = random.random()
                # if parameters.hopeless_attack_parameter * my_ships < enemy_ships and self.me.kore > 100 and self.board.step > 180 and probe_prob > parameters.attack_random_param:
                #     print(f"Step {self.board.step} Not worth attacking shipyard {s.position}")
                #     task = {"id": s.id, "type": "spawn_max", "request_time": self.board.step, "reserved": -1,
                #              "reserve_type": 0, "priority": parameters.LAY_IN_WAIT_PRIORITY}
                #     print("laying in wait!!!!!!!!!")
                #     s.push_task(task)
                #     return False
                #     # enemy_sys = sutils.find_nearby_player_shipyards(self.board, s.position, parameters.lay_in_wait_radius, self.get_enemy().shipyards)
                #     # if len(enemy_sys) > 0 and self.board.step > 200:
                #     #     task = {"id": s.id, "type": "spawn_max", "request_time": self.board.step, "reserved": -1,
                #     #             "reserve_type": 0, "priority": parameters.LAY_IN_WAIT_PRIORITY}
                #     #     print("laying in wait!!!!!!!!!")
                #     #     s.push_task(task)
                #     #     return True
                # else:

                if s.ship_count > 1.2 * defense and steps <= 10 and self.board.step > 180 and self.me.kore > 1000 or my_ships > enemy_ships + 300:
                    if ATTACK_LOGGING:
                        print(f"{self.board.step} Attack! {s.position} at {target.position}.")
                    task = {"type": "attack_shipyard", "request_time": self.board.step, "location": target.position,
                            "reserved": s.ship_count,
                            "reserve_type": 1, "priority": parameters.ATTACK_PRIORITY, "id": s.id}
                    s.push_task(task)

    def assign_unstoppable_attack(self) -> bool:

        enemy = self.get_enemy()
        enemy_shipyards = enemy.shipyards
        # find indefensible shipyards
        for s in self.shipyards:
            if not self.should_attack(s):
                continue

            for e in enemy_shipyards:

                steps = sutils.manhattan_distance(self.board, s.position, e.position)

                if len(enemy_shipyards) > 10 and steps > 10:
                    continue

                # get shipyards near e.
                friendly_count = 0
                friendly_sys = []
                friendly_sys = sutils.find_nearby_player_shipyards(self.board, e.position, steps, self.shipyards)
                friendly_count = 0
                for fs in friendly_sys:
                    if is_attacking(fs):
                        continue
                    if fs.position != s.position and fs.ship_count >= 21:
                        friendly_count += fs.ship_count
                most_defense_can_get = sutils.amount_of_defense_in_n_steps(self.board, steps, e, self.get_enemy())
                if most_defense_can_get + 10 < s.ship_count + friendly_count:
                    if ATTACK_LOGGING:
                        print(
                            f'Turn: {self.board.step}, Unstoppable attack, Target: {e.position}'
                            f' Most defense can get: {most_defense_can_get}')
                        print(
                            f'Initiated by {s.position}, distance {steps}, ship count {s.ship_count},'
                            f' friendly_count: {friendly_count}')

                    unstoppable_priority = parameters.UNSTOPPABLE_ATTACK_PRIORITY - e.max_spawn / 10
                    task = {"type": "attack_shipyard", "request_time": self.board.step, "location": e.position,
                            "reserved": s.ship_count,
                            "reserve_type": 1, "priority": unstoppable_priority, "id": s.id}

                    s.push_task(task)

                    for fs in friendly_sys:
                        if is_attacking(fs) or fs.position == s.position:
                            continue
                        fs_dist = sutils.manhattan_distance(self.board, fs.position, e.position)
                        wait_time = steps - fs_dist
                        task = {"type": "attack_shipyard", "request_time": self.board.step + wait_time,
                                "location": e.position,
                                "reserved": fs.ship_count + wait_time * fs.max_spawn,
                                "reserve_type": 1, "priority": unstoppable_priority, "id": fs.id}
                        fs.push_task(task)

                    return True

    def assign_snipe(self) -> None:
        for s in self.shipyards:
            if s.ship_count >= 40:

                f, target, fs, wait_time = self.snipe_nearby_fleet(s)

                if f and 2 * fs + 1 < s.ship_count and wait_time <= 2:
                    task = {"type": "snipe", "location": target, "request_time": self.board.step + wait_time,
                            "reserved": 2 * fs + 1,
                            "reserve_type": 1, "priority": parameters.SNIPE_PRIORITY, "id": s.id}
                    s.push_task(task)
                    s.assign_path.append("snipe")
                    print("SNIPING", "time now", self.board.step, "wait for", wait_time, "target", target, 2 * fs + 1)

    def assign_expanders(self) -> bool:
        if not self.should_expand():
            return False

        m_count = 50
        candidate = None
        for s in self.shipyards:
            if s.is_expanding():
                continue
            s_count = self.get_shipyards_total_ship_count(s)
            if s_count > m_count:
                positions = self.find_best_position_for_shipyards()
                if positions is None:
                    continue
                candidate = s
                m_count = s_count

        if candidate is not None:
            fleets = self.me.fleets
            turns = parameters.MAX_WAIT_TIME_TO_EXPO + 1
            for i in range(0, parameters.MAX_WAIT_TIME_TO_EXPO):
                num = sutils.number_of_returning_ships(self.board, fleets, candidate.position, i) + candidate.ship_count
                spawn = self.me.kore // 10
                spawn = min(candidate.max_spawn * 4, spawn)
                if num + spawn >= 50:
                    turns = i
                    break
            if turns > parameters.MAX_WAIT_TIME_TO_EXPO:
                if EXPO_LOGGING:
                    print(
                        f"{self.board.step} Could not expo because no one was ready withing",
                        f" {parameters.MAX_WAIT_TIME_TO_EXPO} turns, could have been in {turns}")
                return False

            task = {"type": "expand", "request_time": self.board.step + turns, "reserved": 50,
                    "reserve_type": 1, "priority": parameters.EXPO_PRIORITY,
                    "id": candidate.id}
            candidate.push_task(task)

            if EXPO_LOGGING:
                print(f"Step: {self.board.step} expo in tasks on turn try expanding on turn {self.board.step + turns}")
            return True

        return False

    def num_expo_planned(self) -> int:
        count = 0
        for s in self.shipyards:
            for p, j, t in s.tasks:
                if t["type"] == "expand":
                    count += t["reserved"]
        return count

    def assign_expand(self, s: shipyard.Shipyard) -> bool:
        start = s.position
        available = s.excess
        if available < 50:
            # logger.debug(f"Step {self.board.step}, could not expand available {available}. Total count {
            # s.ship_count}")
            return False
        if parameters.USE_EXPO_LOCATIONS:
            me_id = self.me.id

            if me_id == 1:
                expo_locations = parameters.expo_locations_p1
            else:
                expo_locations = parameters.expo_locations_p0

            if len(expo_locations) == 0:
                end = self.find_best_position_for_shipyards()
                if end is None:
                    print("could not find expo location")
                    return False
                if expo_locations is None:
                    return False
            else:
                end = expo_locations[0]
                expo_locations.pop(0)
                if me_id == 1:
                    parameters.expo_locations_p1 = expo_locations
                else:
                    parameters.expo_locations_p0 = expo_locations

        else:
            end = self.find_best_position_for_shipyards()
            if end is None:
                print("could not find expo location")
                return False

        base_size = min(50, available)
        if base_size < 50:
            return False
        base_size = s.excess
        p = sutils.go_make_a_base(start, end)
        fp = p.get_compact_path()
        s.last_assigned = "Expansion!!"
        s.assigned = True
        if EXPO_LOGGING:
            print(f"Turn {self.board.step} at {s.position} Expanding location: {end}")
            print(f"Turn {self.board.step} at {s.position} Expanding location: {end}")
        s.assign_path.append("expanding")
        self.intended_expos[s.position] = 1
        return self.launch(s, fp, base_size)

    def assign_defend(self, s: shipyard.Shipyard, task: Dict[str, int]) -> bool:
        reserved = task["reserved"]
        end = task["location"]
        amount = min(s.ship_count, reserved)
        if amount < reserved:
            if DEFENSE_LOGGING:
                print(
                    f"Error: ship_count {s.ship_count} less than {reserved} {s.position} DEFENDING location {end} board.step {self.board.step} amount {amount}")
            return False

        start = s.position
        # fp = sutils.L_connecting_two_pos(start, end)
        fp = sutils.find_path_connecting_two_points(self.board, start, end, self.shipyards, search_rad=5)
        # print(f"{self.board.step} using the new path find {fp.get_compact_path()}")
        fp = fp.get_compact_path()
        s.assign_path.append("Defending launching")
        if DEFENSE_LOGGING:
            print(f"Step {self.board.step}: {s.position} DEFENDING location {end} amount {amount}")
        return self.launch(s, fp, amount)

    def attack_shipyard(self, s: shipyard.Shipyard, task: Dict[str, int]) -> bool:
        reserved = task["reserved"]
        location = task["location"]
        amount = min(s.ship_count, reserved, s.excess)
        if amount < 8:
            return False
        start = s.position
        fp = sutils.L_connecting_two_pos(start, location)
        fp = fp.get_compact_path()
        s.assign_path.append("attack shipyard")
        return self.launch(s, fp, amount)

    def get_shipyard_by_id(self, sid: int) -> Union[shipyard.Shipyard, None]:
        for s in self.shipyards:
            if s.id == sid:
                return s
        print("SOMETHING REALLY SCREWEY")
        print(sid)
        print("my records")
        for s in self.shipyards:
            print(s.id)
        print("official record")
        for s in self.me.shipyards:
            print(s.id)

        return None

    def can_we_defend(self, target_s: shipyard.Shipyard, fleet: Dict[str, int]) -> bool:
        attack_time = fleet["step"]
        fleet_size = fleet["size"]
        fleets = self.me.fleets
        nearby_shipyards = []

        num = sutils.number_of_returning_ships(self.board, fleets, target_s.position,
                                               fleet["step"] - self.board.step)

        max_target_can_spawn = min((target_s.max_spawn * (attack_time - self.board.step)),
                                   self.kore / self.config.spawnCost)
        max_target_can_get = int(max_target_can_spawn) + num + target_s.ship_count

        for s in self.shipyards:
            if s == target_s:
                continue
            distance = sutils.manhattan_distance(self.board, s.position, target_s.position)
            nearby_shipyards.append((s, distance))

        nearby_shipyards = sorted(nearby_shipyards, key=lambda x: x[1])
        needed = fleet_size - max_target_can_get
        if needed <= 0:
            return True
        for s, distance in nearby_shipyards:

            request_steps = attack_time - distance - self.board.step
            if request_steps < -2:
                break
            if request_steps < 0:
                request_steps = 1

            # does not take into account how much can spawsn to defend
            num_r = sutils.number_of_returning_ships(self.board, fleets, s.position,
                                                     request_steps)
            num_r += s.ship_count
            if num_r < 8:
                continue

            num_r = min(num_r, needed)

            needed -= num_r

            if needed <= 0:
                return True

        return False

    def cannot_defend_abandon_ship(self, s: shipyard.Shipyard, attack_time: int) -> bool:
        task = {"type": "abandon", "request_time": attack_time,
                "reserved": s.ship_count + 500, "reserve_type": 1, "priority": parameters.ABANDON_PRIORITY,
                "id": s.id, }
        s.push_task(task)
        return False

    def abandon(self, s: shipyard.Shipyard) -> bool:

        amount = s.ship_count
        min_dist = 42
        target_s = None
        for sy in self.shipyards:
            if s == sy:
                continue
            distance = sutils.manhattan_distance(self.board, sy.position, s.position)
            if distance < min_dist:
                min_dist = distance
                target_s = sy
        if target_s is not None:
            fp = sutils.find_path_connecting_two_points(self.board, s.position, target_s.position, self.shipyards,
                                                        search_rad=5)
        else:
            return False
        if DEFENSE_LOGGING:
            print(f"{self.board.step}: location {s.position}. Sending abandon fleet {fp.get_compact_path()}")
        fp = fp.get_compact_path()
        return self.launch(s, fp, amount)

    def assign_defenders(self, fi: fleet_info.FleetInfo, board: kf.Board) -> None:

        defense_priority = parameters.DEFEND_PRIORITY
        attacking_fleets = sutils.under_attack(self.board, self.get_enemy().fleets)

        for f in attacking_fleets:

            fleet = attacking_fleets[f]
            s_id = fleet["target"]
            fleet_size = fleet["size"]
            target_s = self.get_shipyard_by_id(s_id)
            attack_time = fleet["step"]

            fleets = self.me.fleets
            if f in fi.enemy_attacking_fleets:
                target_s.delete_task(f)
                for sy in self.shipyards:
                    sy.delete_task(f)
            if not self.can_we_defend(target_s, fleet):
                if DEFENSE_LOGGING:
                    print(f"{self.board.step} cannot defend {target_s.position}")
                self.cannot_defend_abandon_ship(target_s, attack_time)
                continue

            num = sutils.number_of_returning_ships(self.board, fleets, target_s.position,
                                                   attack_time - board.step)

            max_target_can_spawn = min((target_s.max_spawn * (attack_time - board.step)),
                                       self.kore / self.config.spawnCost)
            max_target_can_get = int(max_target_can_spawn) + num + target_s.ship_count

            defense_priority = parameters.DEFEND_PRIORITY - target_s.max_spawn / 10

            if DEFENSE_LOGGING:
                print("max target can get from returning:", num, "max can spawn:", max_target_can_spawn)

            task_id = f
            task = {"type": "spawn_max_defense", "request_time": attack_time,
                    "reserved": fleet_size, "reserve_type": 1, "priority": defense_priority,
                    "id": target_s.id, "task_id": task_id}
            target_s.push_task(task)

            target_s.defending = True

            fi.enemy_attacking_fleets[f] = {"target": s_id, "size": fleet_size, "task_id": task_id}

            if DEFENSE_LOGGING:
                print("Incoming attack size ", fleet_size, " detected at step: ", board.step, "hits", attack_time,
                      max_target_can_get)

            if max_target_can_get < fleet_size:
                if DEFENSE_LOGGING:
                    print("need", fleet_size - max_target_can_get + 10, "at", target_s.position)
                needed = fleet_size - max_target_can_get + 10

                nearby_shipyards = []
                for s in self.shipyards:
                    if s == target_s:
                        continue
                    distance = sutils.manhattan_distance(self.board, s.position, target_s.position)
                    nearby_shipyards.append((s, distance))

                nearby_shipyards = sorted(nearby_shipyards, key=lambda x: x[1])

                for s, distance in nearby_shipyards:

                    request_time = max(fleet["step"] - distance, board.step)
                    request_step = request_time - board.step
                    if request_step < 0:
                        request_time = 1
                    num_r = sutils.number_of_returning_ships(self.board, fleets, s.position,
                                                             request_step)
                    num_r += s.ship_count
                    num_r = min(num_r, needed)
                    needed -= num_r
                    if num_r < 8:
                        num_r = 8
                    task = {"type": "defend", "request_time": request_time,
                            "location": target_s.position,
                            "reserved": num_r, "reserve_type": 1,
                            "priority": defense_priority, "id": s.id, "task_id": task_id}
                    s.push_task(task)
                    s.defending = True
                    if DEFENSE_LOGGING:
                        print(
                            f"Turn {self.board.step} {s.position} trying to defend at turn {request_time} against attack at {attack_time} target {target_s.position}, amount {num_r}")

                    if needed <= 0:
                        break

        return

    def num_expansions_in_tasks(self) -> int:
        count = 0
        for s in self.shipyards:
            for t in s.tasks:
                if t["type"] == "expand":
                    count += 1

        return count

    def can_spend_incoming_kore(self, spend_turns: int) -> bool:

        if self.board.step > 150:
            debug = 1
        kore_next_turns = [self.me.kore]
        for n in range(1, spend_turns):
            kore_coming_in = sutils.amount_of_kore_returning_in_n_steps(self.board, self.board.current_player, n)
            kore_next_turns.append(kore_coming_in)

        kore_increases = [kore_next_turns[0], kore_next_turns[1]]
        for i in range(2, len(kore_next_turns)):
            kore_increases.append(kore_next_turns[i] - kore_next_turns[i - 1])

        kore_excess = []
        kore_left = kore_increases[0]

        most_can_spawn = sutils.max_can_spawn_on_turn_n(self.board, self.shipyards, self.board.step)

        kore_left -= most_can_spawn * 10
        if kore_left < 0:
            kore_left = 0
        kore_excess.append(kore_left)

        for i in range(1, len(kore_increases)):
            if kore_increases[i] > 0:
                kore_left += kore_increases[i]
                kore_excess.append(kore_left)
            else:
                most_can_spawn = sutils.max_can_spawn_on_turn_n(self.board, self.shipyards, self.board.step + i)
                kore_left -= most_can_spawn * 10

                if kore_left < 0:
                    kore_left = 0
                kore_excess.append(kore_left)

        max_number_consecutive_turns_excess_big = 0
        big = 0
        turns = 0
        for i in range(0, len(kore_excess)):
            if kore_excess[i] > big:
                turns += 1
                if turns > max_number_consecutive_turns_excess_big:
                    max_number_consecutive_turns_excess_big = turns
            else:
                turns = 0

        if max_number_consecutive_turns_excess_big > 5:
            return False

        return True

    def should_expand(self) -> bool:

        num_pending_expos = num_fleets_expanding(self.me.fleets) + self.num_expansions_in_tasks()

        if len(self.shipyards) < 10 and num_pending_expos > 0:
            if EXPO_LOGGING:
                print(f"{self.board.step} Less than 10 shipyards and already expanding")
            return False

        num_sys = 1 + len(self.true_expos) + num_pending_expos
        my_ship_count = sutils.get_total_ships(self.shipyards, self.me.fleets)

        if my_ship_count < 500:
            support_crew_needed = (num_sys + 1) * 60 + 60 * (math.tanh(num_sys / 20))

            if support_crew_needed > my_ship_count:
                if EXPO_LOGGING:
                    print(f"{self.board.step} Not enough support crew")
                return False

        enemy = self.get_enemy()
        enemy_sys = len(enemy.shipyards) + num_fleets_expanding(enemy.fleets)
        enemy_ship_count = sutils.get_total_ships(enemy.shipyards, enemy.fleets)

        if num_sys > enemy_sys and my_ship_count < enemy_ship_count:
            if EXPO_LOGGING:
                print(f"{self.board.step} Have more shipyards than enemy but less ships")
            return False

        if my_ship_count > 500 and self.me.kore > 500:
            if EXPO_LOGGING:
                print(f"{self.board.step} Lets expo")
            return True
        if self.can_spend_incoming_kore(20):
            if EXPO_LOGGING:
                print(f"{self.board.step} Can spend all kore just fine in 20 turns")
            return False
        if EXPO_LOGGING:
            print(f"{self.board.step} Lets expo")
        return True

    def spawn_max(self, s: shipyard.Shipyard) -> bool:
        # max spawn
        if self.board.step >= 390 and len(self.shipyards) > 5:
            s.assign_path.append("not spawning turn limit")
            return False
        spawn_amount = min(self.kore // self.config.spawnCost, s.max_spawn)
        if spawn_amount == 0:
            logging.debug(
                f"{self.board.step} Supposed to spawn max but i guess not enough money??, {self.kore}")
            s.assign_path.append("Not spawning. out of money")
            return False
        kore_to_spend = spawn_amount * self.config.spawnCost
        self.kore -= kore_to_spend
        s.this_turn_action = kf.ShipyardAction.spawn_ships(int(spawn_amount))
        s.assign_path.append("spawned max")
        s.assigned = True
        return True

    def launch(self, s: shipyard.Shipyard, fp: str, amount: int) -> bool:
        amount = int(amount)
        error_check = True

        if error_check:

            # if amount > 45: logger.debug(f"{self.board.step} {s.position}Launching with {amount} ships at {fp},
            # {s.get_conditional()}, {s.excess}, {s.last_assigned}")
            if amount > s.excess and s.get_conditional() is None:
                print(
                    f"{self.board.step} Trying to launch woth more than s.excess. Launching with {amount} ships , {s.get_conditional()}, {s.excess}, {s.last_assigned}")
            for t in s.tasks:
                if t["request_time"] > self.board.step + 50:
                    print(f"{t['request_time']}", self.board.step)
            if s.ship_count < amount or amount < 8:
                print(f"---{self.board.step}, {fp}, amount {amount}, {s.ship_count}, {s.assign_path}")
                return False

        if amount < sutils.min_ship_count_for_flight_plan_len(len(fp)):
            return False
        assert type(fp) == str
        s.this_turn_action = kf.ShipyardAction.launch_fleet_with_flight_plan(amount, fp)
        # print(self.board.step, "Launch", fp)
        s.assigned = True
        s.assign_path.append(fp)
        return True

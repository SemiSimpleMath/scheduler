import heapq as hq
import random
from typing import List

import numpy as np
import statistics
import logging
import inspect
import datetime
import kaggle_environments.envs.kore_fleets.helpers as kf
import path_class
import parameters
import math
import json
import kaggle_environments
DIR_MAP = {
    'N': kf.Point(0, 1),
    'S': kf.Point(0, -1),
    'E': kf.Point(1, 0),
    'W': kf.Point(-1, 0)
}

DIRS = 'NESW'
LENS = '123456789'

KORE_REGEN_FACTOR = [.1 * 1.02 ** i for i in range(80)]

print(f"{__name__} {parameters.VERSION}")

class PerfLogger:

    def __init__(self, logger: logging.Logger):
        self._last = None
        self._current = None
        self.count = 0
        self.enabled = True
        self.logger = logger
        self.log_level = logging.DEBUG

    @property
    def last(self):
        return self._last

    @property
    def current(self):
        return self._current

    def update_current(self):
        self._last = self._current
        self._current = datetime.datetime.utcnow()

    def log(self, msg=''):
        if not self.enabled:
            return
        self.update_current()
        if self.last is not None:
            elapsed = (self.current - self.last).total_seconds()
            fname = inspect.currentframe().f_back.f_code.co_name
            self.logger.log(
                self.log_level,
                f"({self.count}) In {fname}, {elapsed:.3f} seconds since previous log: {msg}"
            )
        self.count += 1


class CacheData:
    def __init__(self):
        self.me = None
        self.enemy = None
        self.enemy_shipyard_positions = {}
        self.points_near = {}
        self.routes = {}
        self.fleet_positions = {}
        self.sy_to_sy_paths = {}
        self.board = None
        self.np_board = None
        self.returning_fleets = {}

    def init_update(self, board):
        return

    def update(self, board):
        self.board = board
        self.board_to_numpy(self.board)
        self.me = board.current_player
        return

    def board_to_numpy(self, board):
        self.np_board = np.zeros((21, 21))
        for x in range(0, 21):
            for y in range(0, 21):
                pos = kf.Point(x, y)
                self.np_board[x, y] = board.cells.get(pos).kore

    def get_numpy_board(self):
        return self.np_board

cache = CacheData()



def manhattan_distance(board, pt1, pt2):
    dist = pt1.distance_to(pt2, board.configuration.size)
    return dist


def get_opposite_dir(d):
    dir_index = DIRS.index(d)
    return DIRS[(dir_index + 2) % 4]


# this is ambiguous because the board is a taurus.  There are two possible segments
# if t is set to true shortest path is returned
def segment_from_pts(pt1, pt2, t=True):
    if not t:
        if pt1[0] != pt2[0] and pt1[1] != pt2[1]:
            return None

        if pt1[0] == pt2[0]:
            diff = pt2[1] - pt1[1]

            if diff < 0:
                direction = "S"
            else:
                direction = "N"
        else:
            diff = pt2[0] - pt1[0]

            if diff < 0:
                direction = "W"
            else:
                direction = "E"

    else:  # use taurus
        if pt1[0] == pt2[0]:  # x values are same so we go N S
            if pt2[1] >= pt1[1]:
                if 2 * (pt2[1] - pt1[1]) > 21:
                    # shortest distance is by South
                    diff = pt1[1] + 21 - pt2[1]
                    direction = "S"
                else:
                    # shortest direction is Nort
                    diff = pt2[1] - pt1[1]
                    direction = "N"
            else:
                if 2 * (pt1[1] - pt2[1]) > 21:
                    # shortest distance is by North
                    diff = pt2[1] + 21 - pt1[1]
                    direction = "N"
                else:
                    # shortest direction is South
                    diff = pt1[1] - pt2[1]
                    direction = "S"
        else:  # Y values are same so we go E W
            if pt2[0] >= pt1[0]:
                if 2 * (pt2[0] - pt1[0]) > 21:
                    # shortest distance is by West
                    diff = pt1[0] + 21 - pt2[0]
                    direction = "W"
                else:
                    # shortest direction is West
                    diff = pt2[0] - pt1[0]
                    direction = "E"
            else:
                if 2 * (pt1[0] - pt2[0]) > 21:
                    # shortest distance is by East
                    diff = pt2[0] + 21 - pt1[0]
                    direction = "E"
                else:
                    # shortest direction is West
                    diff = pt1[0] - pt2[0]
                    direction = "W"

    return path_class.PathSegment(pt1, direction, abs(diff))


def contains_obstacles(p, board):
    # todo This is not done.  Will get around to it tomorrow
    shipyards = board.shipyards
    me = board.current_player
    enemy = None
    players = board.players
    for player in players:
        if player.id != me.id:
            enemy = player

    pts = p.get_coords()
    contains_unwanted_shipyard(board, pts, shipyards)
    path_intersects_friendly_fleet()
    path_intersects_fleet()
    return


def L_connecting_two_pos(start, end, avoid_obstacles=False):
    # find if the points lie on same line

    if start[1] == end[1]:
        path = segment_from_pts(start, end, True)
        return path_class.Path([path])
    if start[0] == end[0]:
        path = segment_from_pts(start, end, True)
        return path_class.Path([path])

    corner = kf.Point(end[0], start[1])

    seg1 = segment_from_pts(start, corner, True)

    seg2 = segment_from_pts(corner, end, True)
    p = path_class.Path([seg1, seg2])
    if avoid_obstacles:
        p1 = path_class.Path([seg1, seg2])
        p2 = path_class.Path([seg2, seg1])

        if contains_obstacles(p1):
            p = p2
        else:
            p = p1

    return p


def one_direction(start, direction):
    path = path_class.PathSegment(start, direction, 0)

    return path


def go_make_a_base(start, end):
    path = L_connecting_two_pos(start, end)
    c = path_class.PathSegment(end, "C", 0)
    path.add_to(c)
    return path


# this is ambiguous because there are two ways to travel from start to end
# and there are two ways to make each segment because of the torus nature of the board
def boomerang_path_from_points(start, end):
    corner = kf.Point(end[0], start[1])

    seg1 = segment_from_pts(start, corner)
    seg2 = segment_from_pts(corner, end)
    seg3 = segment_from_pts(end, corner)
    seg4 = segment_from_pts(corner, start)

    path = path_class.Path([seg1, seg2, seg3, seg4])

    return path


def one_way_path(start, d):
    dist = 21
    seg1 = path_class.PathSegment(start, d, dist)
    path = path_class.Path([seg1])
    return path


def yoyo_path(board, start, d, dist):
    seg1 = path_class.PathSegment(start, d, dist)
    end1 = seg1.get_end(board)
    seg2 = path_class.PathSegment(end1, get_opposite_dir(d), dist)
    path = path_class.Path([seg1, seg2])
    return path


def boomerang_path(board, start, direction1, distance1, direction2, distance2):
    seg1 = path_class.PathSegment(start, direction1, distance1)
    end1 = seg1.get_end(board)
    seg2 = path_class.PathSegment(end1, direction2, distance2)
    end2 = seg2.get_end(board)
    seg3 = path_class.PathSegment(end2, get_opposite_dir(direction2), distance2)
    seg4 = path_class.PathSegment(end1, get_opposite_dir(direction1), distance1)

    path = path_class.Path([seg1, seg2, seg3, seg4])

    return path


"""
start and corner are diagonally opposite corners.
Here the shipyard is one of the corners.
Rectangles where shipyard is just part of one of the sides are
more complicated.
"""


def rectangle_path(board, start, direction1, distance1, direction2, distance2):
    seg1 = path_class.PathSegment(start, direction1, distance1)
    end1 = seg1.get_end(board)
    seg2 = path_class.PathSegment(end1, direction2, distance2)
    end2 = seg2.get_end(board)
    seg3 = path_class.PathSegment(end2, get_opposite_dir(direction1), distance1)
    end3 = seg3.get_end(board)
    seg4 = path_class.PathSegment(end3, get_opposite_dir(direction2), distance2)

    path = path_class.Path([seg1, seg2, seg3, seg4])
    return path


def new_pt_by_distance(board, start, x, y):
    if x < 0:
        dir_x = "W"
    else:
        dir_x = "E"
    if y < 0:
        dir_y = "S"
    else:
        dir_y = "N"

    for _ in range(abs(x)):
        start = start.translate(DIR_MAP[dir_x], board.configuration.size)

    for _ in range(abs(y)):
        start = start.translate(DIR_MAP[dir_y], board.configuration.size)
    return start


def generate_all_boomerangs(start, board, max_length=None):
    paths = []
    d1, d2 = "N", "N"
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if dir1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"
        for dir2 in range(0, 4):
            if dir2 == dir1 or dir2 == DIRS.index(get_opposite_dir(d1)):
                continue
            if dir2 == 0:
                d2 = "N"
            if dir2 == 1:
                d2 = "E"
            if dir2 == 2:
                d2 = "S"
            if dir2 == 3:
                d2 = "W"

        for dist1 in range(1, 10):
            for dist2 in range(1, 10):
                if 2 * (dist1 + dist2) > max_length:
                    continue
                paths.append(boomerang_path(board, start, d1, dist1, d2, dist2))

    return paths


def generate_crowbars(start, board, max_length=None):
    paths = []
    d1, d2 = -1, -1
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if dir1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"
        for dir2 in range(0, 4):
            if dir2 == dir1 or dir2 == DIRS.index(get_opposite_dir(d1)):
                continue
            if dir2 == 0:
                d2 = "N"
            if dir2 == 1:
                d2 = "E"
            if dir2 == 2:
                d2 = "S"
            if dir2 == 3:
                d2 = "W"

        for dist in range(1, 10):  # dist < max_length // 2 -1
            if 2 + 2 * dist > max_length:
                continue
            paths.append(boomerang_path(board, start, d1, 1, d2, dist))

    return paths


def generate_unit_squares(start, board):
    paths = generate_all_rectangles(start, board, max_length=4)
    return paths


def generate_flat_rectangles(start, board, max_length):
    d1 = ""
    d2 = ""
    paths = []
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if dir1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"

        for dir2 in range(0, 4):
            if dir2 == dir1 or dir2 == DIRS.index(get_opposite_dir(d1)):
                continue
            if dir2 == 0:
                d2 = "N"
            if dir2 == 1:
                d2 = "E"
            if dir2 == 2:
                d2 = "S"
            if dir2 == 3:
                d2 = "W"

            for dist in range(1, 10):
                if 2 * dist + 2 > max_length:
                    continue
                paths.append(rectangle_path(board, start, d1, 1, d2, dist))

    return paths


def generate_yoyos(start, board, max_length):
    d1 = ""
    paths = []
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if dir1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"
        for dist in range(0, min(10, max_length // 2)):
            paths.append(yoyo_path(board, start, d1, dist))
    return paths


def generate_all_one_ways(start, board):
    paths = []
    d = ""
    for dir1 in range(0, 4):
        if dir1 == 0:
            d = "N"
        if dir1 == 1:
            d = "E"
        if dir1 == 2:
            d = "S"
        if dir1 == 3:
            d = "W"

        paths.append(one_way_path(start, d))
    return paths


def generate_all_rectangles(start, board, max_length=None):
    d1 = ""
    d2 = ""
    paths = []
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if dir1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"

        for dir2 in range(0, 4):
            if dir2 == dir1 or dir2 == DIRS.index(get_opposite_dir(d1)):
                continue
            if dir2 == 0:
                d2 = "N"
            if dir2 == 1:
                d2 = "E"
            if dir2 == 2:
                d2 = "S"
            if dir2 == 3:
                d2 = "W"

            for dist1 in range(1, 10):
                for dist2 in range(1, 10):
                    if 2 * (dist1 + dist2) > max_length:
                        continue
                    paths.append(rectangle_path(board, start, d1, dist1, d2, dist2))

    return paths

def generate_all_one_shifted_rectangles(board, start, max_length):

    d1 = ""
    d2 = ""
    paths = []
    for dir1 in range(0, 4):
        if dir1 == 0:
            d1 = "N"
        if d1 == 1:
            d1 = "E"
        if dir1 == 2:
            d1 = "S"
        if dir1 == 3:
            d1 = "W"

        for dir2 in range(0, 4):
            if dir2 == dir1 or dir2 == DIRS.index(get_opposite_dir(d1)):
                continue
            if dir2 == 0:
                d2 = "N"
            if dir2 == 1:
                d2 = "E"
            if dir2 == 2:
                d2 = "S"
            if dir2 == 3:
                d2 = "W"

            d3 = get_opposite_dir(d2)
            d4 = get_opposite_dir(d1)

            for dist1 in range(1, 10):
                for dist2 in range(1, 10):
                    if 2 * (dist1 + dist2) + 2> max_length:
                        continue

                    seg1 = path_class.PathSegment(start, d1,1)
                    end1 = seg1.get_end(board)
                    seg2 = path_class.PathSegment(end1, d2, dist1)
                    end2 = seg2.get_end(board)
                    seg3 = path_class.PathSegment(end2, d3, dist2)
                    end3 = seg3.get_end(board)
                    seg4 = path_class.PathSegment(end3, d4, 1)

                    paths.append(path_class.Path([seg1, seg2, seg3, seg4]))

    return paths



def kore_in_flight_path(board, flight_path, collection_rate):
    total_kore = 0
    steps = 0
    for pos in flight_path:
        steps += 1
        kore = (board.cells.get(pos).kore * KORE_REGEN_FACTOR[steps] or 0) * collection_rate
        total_kore += kore
    return total_kore


# ref @egrehbbt
def collection_rate_for_ship_count(ship_count):
    return min(math.log(ship_count) / 20, 0.99)


def is_close(a, b, epsilon):
    if abs(a - b) < epsilon:
        return True
    return False


def generate_return_path_with_most_kore(board, s, shipyards, start, max_length=40):
    paths_34 = []
    paths_21 = []
    paths_13 = []
    paths_8 = []

    paths_np_34 = []
    paths_np_21 = []
    paths_np_13 = []
    paths_np_8 = []

    p_scores_34 = []
    p_scores_21 = []
    p_scores_13 = []

    # Orbit eg. N needs fleet size 1 Note: this has length 21. Call these one_ways
    # Sneak peak eg NS needs fleet size. Has length 2
    # Yoyo eg. N3S needs fleet size 3: has length 2*dist. Yoyo includes sneak peak
    # Unit square needs 5 fleet. Has length 4
    # Flat rectangle needs 8. Has length 2*dist + 2, flat rectangle includes unit square
    # Crowbar eg. NE2W2S Needs 13 has length 2*dist + 2.
    # Rectangle and boomerang need 21. Have dist 2*dist1 + 2 * dist2

    # Rectangle and boomerang cover flat rectange, unit square, and crowbar.

    # yoyo, flat_rectangle, unit square and crowbar should be also in paths_13
    # yoyo and one way should be in paths_21
    # all paths_21 should be in paths_34

    # yoyo and one way belong also in paths 8

    if (start, max_length) not in cache.routes:

        #one_shifted_rectangles = generate_all_one_shifted_rectangles(board, start, max_length)
        boomerangs = generate_all_boomerangs(start, board, max_length)
        rectangles = generate_all_rectangles(start, board, max_length)
        yoyos = generate_yoyos(start, board, max_length)

        one_ways = []
        if max_length >= 21:
            one_ways = generate_all_one_ways(start, board)

        crowbars = generate_crowbars(start, board, max_length)
        flat_rectangles = generate_flat_rectangles(start, board, max_length)

        if len(shipyards) < 10:
            radius = 15
        else:
            radius = 10

        sy_paths = []
        if parameters.USE_SY_PATHS:
            if len(shipyards) <= 10:
                sy_paths = find_shipyard_to_shipyards_paths(board, s, shipyards, radius)

        paths_21 += boomerangs[:]
        paths_21 += rectangles[:]
        paths_21 += yoyos[:]
        paths_21 += one_ways[:]

        if parameters.USE_SY_PATHS:
            if max_length >= 35:
                paths_21 += sy_paths

        paths_8 += flat_rectangles[:]
        paths_8 += yoyos[:]
        paths_8 += one_ways[:]

        paths_13 += crowbars[:]
        paths_13 += paths_8[:]

        paths_34 += paths_21[:]
        #paths_34 += one_shifted_rectangles[:]

        if len(paths_34) > 0:
            for p in paths_34:
                p1 = p.coords_to_numpy(board) * collection_rate_for_ship_count(34) / 34
                paths_np_34.append(p1)

            paths_np_34 = np.stack(paths_np_34)

        if len(paths_21) > 0:
            for p in paths_21:
                p1 = p.coords_to_numpy(board) * collection_rate_for_ship_count(21) / 21
                paths_np_21.append(p1)

            paths_np_21 = np.stack(paths_np_21)

        if len(paths_13) > 0:
            for p in paths_13:
                p1 = p.coords_to_numpy(board) * collection_rate_for_ship_count(13) / 13
                paths_np_13.append(p1)
            paths_np_13 = np.stack(paths_np_13)

        for p in paths_8:
            p1 = p.coords_to_numpy(board) * collection_rate_for_ship_count(8) / 8
            paths_np_8.append(p1)

        paths_np_8 = np.stack(paths_np_8)

        cache.routes[(start, max_length)] = (
            paths_34, paths_np_34, paths_21, paths_np_21, paths_13, paths_np_13, paths_np_8, paths_8)

    else:

        (paths_34, paths_np_34, paths_21, paths_np_21, paths_13, paths_np_13, paths_np_8, paths_8) = cache.routes[
            (start, max_length)]

    ranked_paths = []

    npb = cache.get_numpy_board()

    if len(paths_np_34) > 0:
        p_scores_34 = paths_np_34 * npb
        p_scores_34 = np.sum(p_scores_34, axis=1)
        p_scores_34 = np.sum(p_scores_34, axis=1)
    if len(paths_np_21) > 0:
        p_scores_21 = paths_np_21 * npb
        p_scores_21 = np.sum(p_scores_21, axis=1)
        p_scores_21 = np.sum(p_scores_21, axis=1)

    if len(paths_np_13) > 0:
        p_scores_13 = paths_np_13 * npb
        p_scores_13 = np.sum(p_scores_13, axis=1)
        p_scores_13 = np.sum(p_scores_13, axis=1)

    p_scores_8 = paths_np_8 * npb
    p_scores_8 = np.sum(p_scores_8, axis=1)
    p_scores_8 = np.sum(p_scores_8, axis=1)

    if len(p_scores_34) > 0:
        for path, score in zip(paths_34, p_scores_34):
            hq.heappush(ranked_paths, (-1000 * score, random.random(), 34, path))
    if len(p_scores_21) > 0:
        for path, score in zip(paths_21, p_scores_21):
            hq.heappush(ranked_paths, (-1000 * score, random.random(), 21, path))
    if len(p_scores_13) > 0:
        for path, score in zip(paths_13, p_scores_13):
            hq.heappush(ranked_paths, (-1000 * score, random.random(), 13, path))

    for path, score in zip(paths_8, p_scores_8):
        hq.heappush(ranked_paths, (-1000 * score, random.random(), 8, path))

    return ranked_paths

def get_closest_enemy_shipyard(board, position, me):
    min_dist = board.configuration.size
    enemy_shipyard = None
    for shipyard in board.shipyards.values():
        if shipyard.player_id == me.id:
            continue
        dist = position.distance_to(shipyard.position, board.configuration.size)
        if dist < min_dist:
            min_dist = dist
            enemy_shipyard = shipyard
    return enemy_shipyard


def find_flight_plans_that_attack_shipyard(board, shipyard):
    me = board.current_player
    position = shipyard.position
    enemy = get_closest_enemy_shipyard(board, position, me)
    if enemy is None:
        return None, 0
    enemy_count = enemy.ship_count
    start = shipyard.position
    end = enemy.position
    fp = L_connecting_two_pos(start, end)
    attack_size = enemy_count + 100
    return fp, attack_size

def under_attack(board, fleets):
    me = board.current_player
    my_shipyards = me.shipyards
    attacking_fleets = {}
    for f in fleets:
        pts = get_pts_on_fleets_path(board, f)
        for sy in my_shipyards:
            if pts[-1] == sy.position:
                attacking_fleets[f.id] = {}
                attacking_fleets[f.id]["size"] = f.ship_count
                attacking_fleets[f.id]["step"] = board.step + len(pts)
                attacking_fleets[f.id]["target"] = sy.id

    return attacking_fleets


def get_fp_last_dir(fp):
    for i in range(len(fp) - 1, -1, -1):
        if fp[i].isdigit():
            continue
        else:
            return fp[i]
    return None


def get_pts_on_fleets_path(board, f):
    pos = f.position
    fp = f.flight_plan
    d = f.direction.to_char()

    r = path_class.Route(d, fp, pos)
    path, expo = r.pts(board)

    shipyards = []
    for k, s in board.shipyards.items():
        shipyards.append(s.position)
    pts = []
    for p in path:
        pts.append(p)
        if p in shipyards:
            return pts

    if not expo:
        direction = get_fp_last_dir(fp)
        if direction is None:
            direction = d
        start = path[-1]
        amount = 21
        extendo = pts_in_direction(board, start, direction, amount)
        for i in range(len(extendo)):
            if extendo[i] in shipyards:
                extendo = extendo[:i + 1]
                pts += extendo
                return pts
        pts += extendo
    return pts


def pts_in_direction(board, start, direction, steps):
    shipyards = []
    for k, s in board.shipyards.items():
        shipyards.append(s.position)

    next_position = start.translate(DIR_MAP[direction], board.configuration.size)
    positions = [next_position]
    for _ in range(steps - 1):
        next_position = positions[-1].translate(DIR_MAP[direction], board.configuration.size)
        positions.append(next_position)
    return positions


# because we cache we need to use board.step as time
def number_of_returning_ships(board, fleets, position, steps):
    count = 0

    for f in fleets:
        if f.id in cache.returning_fleets:
            final_pos = cache.returning_fleets[f.id]["final_pos"]
            arrival_time = cache.returning_fleets[f.id]["arrival_time"]

        else:
            path = get_pts_on_fleets_path(board, f)
            final_pos = path[-1]
            arrival_time = len(path) + board.step
            cache.returning_fleets[f.id] = {}
            cache.returning_fleets[f.id]["final_pos"] = final_pos
            cache.returning_fleets[f.id]["arrival_time"] = arrival_time

        if final_pos == position:
            if arrival_time <= steps + board.step:
                count += f.ship_count
    return count


def amount_of_kore_returning_in_n_steps(board, player, steps):

    total = 0
    fleets = player.fleets
    path = []
    for f in fleets:
        if f.id in cache.returning_fleets:
            arrival_time = cache.returning_fleets[f.id]["arrival_time"]

        else:
            path = get_pts_on_fleets_path(board, f)
            final_pos = path[-1]
            arrival_time = len(path) + board.step
            cache.returning_fleets[f.id] = {}
            cache.returning_fleets[f.id]["final_pos"] = final_pos
            cache.returning_fleets[f.id]["arrival_time"] = arrival_time

        if arrival_time <= steps + board.step:
            total += f.kore
            if len(path) == 0:
                path = get_pts_on_fleets_path(board, f)
            total += kore_in_flight_path(board, path, f.collection_rate)

    return total


def returning_fleets_in_n_turns(board, fleets, position, steps):
    returning_fleets = []
    for f in fleets:
        if (f.id, board.step + steps) in cache.returning_fleets:
            final_pos = cache.returning_fleets[(f.id, board.step + steps)]["final_pos"]
            arrival_time = cache.returning_fleets[(f.id, board.step + steps)]["arrival_time"]

        else:
            path = get_pts_on_fleets_path(board, f)
            final_pos = path[-1]
            arrival_time = len(path)
            cache.returning_fleets[(f.id, board.step + steps)] = {}
            cache.returning_fleets[(f.id, board.step + steps)]["final_pos"] = final_pos
            cache.returning_fleets[(f.id, board.step + steps)]["arrival_time"] = arrival_time
        if final_pos == position:
            if arrival_time <= steps:
                returning_fleets.append(f)
    return returning_fleets


def check_path_safety(board, path, fleets):
    amount = 0

    for f in fleets:
        i, size = path_intersects_fleet(board, path, f)
        if i:
            amount += size
    if amount > 0:
        return True, amount
    return False, None


def adjacent_pts(board, pt1, pt2):
    if manhattan_distance(board, pt1, pt2) == 1:
        return True
    return False


def path_intersects_fleet(board, path, fleet):
    path = path.get_coords(board)
    pts = get_pts_on_fleets_path(board, fleet)

    for i in range(len(path)):

        if i >= len(pts):
            return False, None

        if path[i] == pts[i] or adjacent_pts(board, path[i], pts[i]):
            return True, fleet.ship_count
    return False, None


def path_intersects_friendly_fleet(board, path, fleet):
    path = path.get_coords(board)
    pts = get_pts_on_fleets_path(board, fleet)

    for i in range(len(path)):

        if i >= len(pts):
            return False, None

        if path[i] == pts[i]:
            return True, fleet.ship_count
    return False, None


# path has to be path object
def paths_overlap(board, path, fleets, threshold1=5, threshold2=2):

    path_pts = path.get_coords(board)

    num_fleets_overlapping = 1
    for f in fleets:
        f_pts = get_pts_on_fleets_path(board, f)
        count = 0
        for p in path_pts:
            if p in f_pts:
                count += 1
            if count > threshold1:
                num_fleets_overlapping += 1
                break
    if num_fleets_overlapping > threshold2:
        return True
    return False


# ref @egrehbbt
def min_ship_count_for_flight_plan_len(flight_plan_len):
    return math.ceil(math.exp((flight_plan_len - 1) / 2))


def find_nearby_shipyards(board, pt, radius):
    shipyards = []
    for k, s in board.shipyards.items():
        if manhattan_distance(board, pt, s.position) < radius:
            shipyards.append(s)

    return shipyards


def find_nearby_shipyards_among_given(board, pt, radius, shipyards):
    sys = []
    for s in shipyards:
        if manhattan_distance(board, pt, s.position) < radius:
            sys.append(s)

    return sys


def find_nearby_player_shipyards(board, pt, radius, shipyards):
    sys = []
    for s in shipyards:
        if manhattan_distance(board, pt, s.position) < radius:
            sys.append(s)

    return sys


def find_nearby_fleets(board, pt, fleets, radius):
    result = []
    for f in fleets:
        if manhattan_distance(board, pt, f.position) < radius:
            result.append(f)

    return result


def get_total_ships(shipyards, fleets):
    ships = 0
    for fleet in fleets:
        ships += fleet.ship_count
    for shipyard in shipyards:
        ships += shipyard.ship_count
    return ships


def average_fleet_size(board, player):
    ships = 0
    for fleet in board.fleets[player]:
        ships += fleet.ship_count
    if ships == 0:
        return ships
    return ships / len(board.fleets[player])


def spawn_rate_at_time(turns_controlled, time, board):
    turns_controlled = turns_controlled + time - board.step
    if turns_controlled < 0:
        print("Error: turns controlled should not be negative.")
        return 0
    if 0 <= turns_controlled < 2:
        return 1
    if 2 <= turns_controlled < 7:
        return 2
    if 7 <= turns_controlled < 17:
        return 3
    if 17 <= turns_controlled < 34:
        return 4
    if 34 <= turns_controlled < 60:
        return 5
    if 60 <= turns_controlled < 97:
        return 6
    if 97 <= turns_controlled < 147:
        return 7
    if 147 <= turns_controlled < 212:
        return 8
    if 212 <= turns_controlled < 294:
        return 9
    if turns_controlled >= 294:
        return 10


def amount_ships_can_spawn_in_n_steps(board, steps, s, kore=999999):
    spawn_num = 0
    for i in range(0, steps):
        spawn_num += spawn_rate_at_time(s._turns_controlled, i + board.step, board)

    spawn_num = min(spawn_num, kore // 10)
    spawn_num = max(spawn_num, 0)
    return spawn_num


def max_can_spawn_on_turn_n(board, shipyards, step):
    total = 0
    for s in shipyards:
        total += spawn_rate_at_time(s._turns_controlled, step + board.step, board)
    return total


def max_amount_of_ships_in_n_steps(board, steps, s, fleets, kore):
    spawn_num = amount_ships_can_spawn_in_n_steps(board, steps, s, kore)
    start_amount = s.ship_count

    ships_coming_in_at_times = number_of_returning_ships(board, fleets, s.position, steps)

    # print(f"start_amount {start_amount}, coming in, {ships_coming_in_at_times}, can spawn {spawn_num}")
    return start_amount + ships_coming_in_at_times + spawn_num


# once the attack starts this is the most that a shipyard can get
# -If they spawn max
# -If the shipyard does not send anything out and waits for incoming ships
# -Same for neighboring shipyards
# -Neighboring shipyards send their fleets to assist just in time.
def amount_of_defense_in_n_steps(board, steps, s, player):

    shipyards = player.shipyards
    fleets = player.fleets
    kore = player.kore
    # print("Number of steps to defend: ", steps)

    # this is what amount is currently in the shipyards.  Some % of this will be sent out.
    static_defense = s.ship_count

    if kore < 500 and len(fleets) < 14:
        # Accuracy of this function needs to be assessed
        kore_in_n_steps = amount_of_kore_returning_in_n_steps(board, player, steps)

        kore += kore_in_n_steps

    else:
        kore = max(2000, kore)

    total = max_amount_of_ships_in_n_steps(board, steps, s, fleets, kore)

    # print(f"Amount of defense of {s.position} at time {board.step} is: {total}")
    kore -= s.max_spawn * 10 * (steps)
    # find shipyards that are at n steps or closer

    close_shipyards = []

    # print(f"Turn is {board.step}, target {s.position}")

    for sy in shipyards:
        if sy == s:
            continue
        if manhattan_distance(board, s.position, sy.position) < steps:
            close_shipyards.append(sy)

    for sy in close_shipyards:
        static_defense += sy.ship_count
        dist = manhattan_distance(board, s.position, sy.position)
        kore -= sy.max_spawn * 10 * (steps - dist)
        max_can_send = max_amount_of_ships_in_n_steps(board, steps - dist, sy, fleets, kore)
        total += max_can_send

    # print(f"max that shipyard {s.position} can get is {total}")
    # how much will be launched and not come back? This is a guess.
    # This could be improved by knowing average length of enemy fleet orbit
    # Also by knowing what the most typical launch sizes are
    return total - .5 * static_defense


def get_fleet_mode(fleets):
    ships = []
    m = 0
    for f in fleets:
        ships.append(f.ship_count)

    if len(ships) > 0:
        m = statistics.mode(ships)

    return m


def get_fleet_median(fleets):
    ships = []
    m = 0
    for f in fleets:
        ships.append(f.ship_count)

    if len(ships) > 5:
        m = statistics.median(ships)
    return m


def get_fleet_top_median(fleets, top):
    ships = []
    if len(fleets) == 0:
        return 0
    for f in fleets:
        ships.append(f.ship_count)

    if len(ships) > top:
        m = statistics.median(ships[-top:])
    else:
        return statistics.median(ships)
    return m


def get_fleet_max(fleets):
    m = 0
    for f in fleets:
        m = max(m, f.ship_count)
    return m


def get_closest_shipyard(board, position, shipyards):
    min_dist = board.configuration.size
    shipyard = None
    for s in shipyards:
        dist = manhattan_distance(board, position, s.position)
        if dist < min_dist:
            min_dist = dist
            shipyard = s
    return shipyard


def path_risk(board, path, my_shipyards, enemy_shipyards):
    #  if time to get to every pt in the path is less than the distance from nearest enemy to the pt in the path then
    # the path is absolutely safe.

    if len(enemy_shipyards) == 0:
        return 0
    path = path.get_coords(board)
    if len(path) < 5:
        return 0
    risk = 0
    step = 0
    for i in range(1, len(path)):
        closest_shipyard = get_closest_shipyard(board, path[i], enemy_shipyards)
        if step >= manhattan_distance(board, path[i], closest_shipyard.position):
            risk += 1
        step += 1

    return risk


def path_risk2(board, path, my_shipyards, enemy_shipyards):
    #  if time to get to every pt in the path is less than the distance from nearest enemy to the pt in the path then
    # the path is absolutely safe.

    if len(enemy_shipyards) == 0:
        return 0
    path = path.get_coords(board)
    if len(path) < 5:
        return 0
    risk = 0

    for i in range(1, len(path)):
        closest_enemy_shipyard = get_closest_shipyard(board, path[i], enemy_shipyards)
        closest_my_shipyard = get_closest_shipyard(board, path[i], my_shipyards)
        if manhattan_distance(board, path[i], closest_enemy_shipyard.position) \
                <= manhattan_distance(board, path[i], closest_my_shipyard.position):
            risk += 1

    return risk


def path_risk3(board, path, my_shipyards, enemy_shipyards):
    # every enemy shipyard near the path should contribute to the risk.
    if len(enemy_shipyards) == 0:
        return 0
    path = path.get_coords(board)
    if len(path) < 10:
        return 0
    risk = 0

    for i in range(4, len(path)):

        closest_my_shipyard = get_closest_shipyard(board, path[i], my_shipyards)
        dist_to_closest = manhattan_distance(board, path[i], closest_my_shipyard.position)
        closest_enemy_shipyards = find_nearby_shipyards_among_given(board, path[i], dist_to_closest + 1,
                                                                    enemy_shipyards)
        if len(closest_enemy_shipyards) > risk:
            risk = len(closest_enemy_shipyards)

    return risk


def contains_unwanted_shipyard(board, fp, shipyards):
    path = fp.get_coords(board)
    sy_pts = []
    for s in shipyards:
        sy_pts.append(s.position)
    for i in range(1, len(path) - 1):
        if path[i] in shipyards:
            return True
    return False


def find_best_path(ranked_paths, ships, ships_min, ships_max, board, my_fleets, enemy_fleets, my_shipyards,
                   enemy_shipyards, avoid_risk=False):
    if len(ranked_paths) == 0:
        print("no paths", ships_min, ships_max, ships)
        return None, -1, 0

    fp = None
    assert ships_min <= ships_max, f"{ships_min}, {ships_max}"

    while True:
        if len(ranked_paths) == 0:
            print("no paths", ships_min, ships_max, ships)
            return None, -1, 0
        index, r, best_size, fp = hq.heappop(ranked_paths)

        if best_size < ships_min or best_size > ships_max:
            continue

        # if contains_unwanted_shipyard(board, fp, my_shipyards):
        #     # print("rejecting because contains unwanted shipyard")
        #     continue
        #
        # if contains_unwanted_shipyard(board, fp, enemy_shipyards):
        #     # print("rejecting because contains unwanted shipyard")
        #     continue

        not_safe = False
        enemy_ships = 21
        if len(enemy_fleets) < 15:
            not_safe, enemy_ships = check_path_safety(board, fp, enemy_fleets)

        if not_safe:
            if avoid_risk:
                continue
            return fp, max(best_size, int(1.5 * enemy_ships)), index

        if len(my_fleets) < 15:
            if paths_overlap(board, fp, my_fleets, parameters.paths_overlap_param1, parameters.paths_overlap_param2):
                continue
        if len(my_shipyards) < 12 and len(enemy_shipyards) < 12:
            risk = path_risk2(board, fp, my_shipyards, enemy_shipyards)
            if risk > 0 and avoid_risk:
                continue
            if risk == 1:
                enemy_median = get_fleet_top_median(enemy_fleets, 10)
                if ships >= int(1.1 * enemy_median + 1):
                    if best_size == 8:
                        continue
                    # print(f"Recommending risk path {best_size}", max(int(1.1 * enemy_median + 1), best_size))
                    return fp, max(int(1.1 * enemy_median + 1), best_size), index
            if risk > 1:
                continue


        # if best_size >= 21: print(f"JJJ  : Step: {board.step} ships {ships}, best_size {best_size}, index, {index},
        # {fp.get_compact_path()}")
        return fp, best_size, index


def find_best_path2(ranked_paths, ships, ships_min, ships_max, board, my_fleets, enemy_fleets, my_shipyards,
                    enemy_shipyards, avoid_risk=False):
    first_choice = 1
    if len(ranked_paths) == 0:
        print("no paths", ships_min, ships_max, ships)
        return None, -1, 0, False

    fp = None
    assert ships_min <= ships_max, f"{ships_min}, {ships_max}"

    while True:
        if len(ranked_paths) == 0:
            print("no paths", ships_min, ships_max, ships)
            return None, -1, 0

        index, r, best_size, fp = hq.heappop(ranked_paths)
        if first_choice == 1:
            first_choice = 0
            # print(f"Sched: first choice Step: {board.step} ships {ships}, best_size {best_size}, index, {index},
            # {fp.get_compact_path()}")
        if best_size < ships_min or best_size > ships_max:
            # print("Rejecting because best_size < min or best_size > min")
            continue

        if contains_unwanted_shipyard(board, fp, my_shipyards):
            # print("rejecting because contains unwanted shipyard")
            continue

        if contains_unwanted_shipyard(board, fp, enemy_shipyards):
            # print("rejecting because contains unwanted shipyard")
            continue

        if len(my_fleets) < 15:
            if paths_overlap(board, fp, my_fleets, 5, 2):
                # print("Rejecting because paths overlap")
                continue

        not_safe = False
        enemy_ships = 21
        if len(enemy_fleets) < 15:
            not_safe, enemy_ships = check_path_safety(board, fp, enemy_fleets)

        if not_safe:
            if avoid_risk:
                # print("Rejecting because avoid risk not safe")
                continue
            best_size = max(best_size, int(1.5 * enemy_ships) + 1)
            if best_size > ships_max:
                # print("Rejecting because it collides and we dont have enough ships")
                continue
            else:
                return fp, max(best_size, int(1.5 * enemy_ships)), index

        if len(my_shipyards) < 12 and len(enemy_shipyards) < 12:
            if 2 > path_risk2(board, fp, my_shipyards, enemy_shipyards) > 0:
                enemy_median = get_fleet_top_median(enemy_fleets, 10)
                if ships >= int(1.1 * enemy_median + 1):
                    if best_size == 8:
                        continue
                    print(f"Recommending risk path {best_size}", max(int(1.1 * enemy_median + 1), best_size))
                    return fp, max(int(1.1 * enemy_median + 1), best_size), index
                else:
                    continue

        if best_size < ships_min or best_size > ships_max:
            continue
        # if best_size >= 21: print(f"Sched: Step: {board.step} Using this one :ships {ships}, best_size {best_size},
        # index, {index}, {fp.get_compact_path()}")
        return fp, best_size, index


def ships_needed_for_fp(fp):
    for i in range(1, 256):
        length = math.floor(2 * math.log(i)) + 1
        if length == len(fp):
            return i


def find_all_pts_within_radius(board: kf.Board, pt: kf.Point, r: float) -> List[kf.Point]:
    if (pt, r) in cache.points_near:
        return cache.points_near[(pt, r)]
    points = []
    if r >= 1:
        for px in range(21):
            for py in range(21):
                distance = manhattan_distance(board, pt, kf.Point(px, py))
                if 0 < distance <= r:
                    points.append(kf.Point(px, py))
    cache.points_near[(pt, r)] = points
    return points


def find_shipyard_to_shipyards_paths(board, shipyard, shipyards, radius):
    destinations = set()
    for s in shipyards:
        if s.position != shipyard.position:
            destinations.add(s)
    if len(destinations) <= 1:
        return []

    paths = []
    for d in destinations:
        paths += find_shipyard_to_shipyard_paths(board, shipyard, d, radius)

    return paths


def reverse_path(board, path):
    if len(path.get_segments()) == 0:
        return []
    reversed_path = []
    segs = path.get_segments()
    end = path.get_segments()[-1].get_end(board)
    for i in range(len(segs) - 1, -1, -1):
        seg = segs[i]
        d = seg.get_direction()
        n = seg.get_length()

        r_d = get_opposite_dir(d)
        new_seg = path_class.PathSegment(end, r_d, n)
        position = end
        for _ in range(n):
            position = position.translate(DIR_MAP[r_d], board.configuration.size)
        end = position
        reversed_path.append(new_seg)
    final_path = path_class.Path(reversed_path)
    return final_path


def reverse_paths(board, paths):
    r_paths = []

    for p in paths:
        r_paths.append(reverse_path(board, p))

    return r_paths


def find_shipyard_to_shipyard_paths(board, begin_s, end_s, radius):
    if (begin_s.id, end_s.id) in cache.sy_to_sy_paths:
        return cache.sy_to_sy_paths[(begin_s.id, end_s.id)]
    elif (end_s.id, begin_s.id) in cache.sy_to_sy_paths:
        reversed_paths = reverse_paths(board, cache.sy_to_sy_paths[(end_s.id, begin_s.id)])
        cache.sy_to_sy_paths[(begin_s.id, end_s.id)] = reversed_paths
        return reversed_paths

    nearby_pts = find_all_pts_within_radius(board, begin_s.position, radius)

    start = begin_s.position
    end = end_s.position
    paths = []
    for c in nearby_pts:
        if c == start or c == end:
            continue

        path1 = L_connecting_two_pos(start, c)
        path2 = L_connecting_two_pos(c, end)
        combines = path1.get_segments() + path2.get_segments()
        path = path_class.Path(combines)

        paths.append(path)

    cache.sy_to_sy_paths[(begin_s.id, end_s.id)] = paths
    cache.sy_to_sy_paths[(end_s.id, begin_s.id)] = reverse_paths(board, paths)

    return paths

def find_path_connecting_two_points(board, start, end, shipyards, search_rad=5):
    nearby_pts = find_all_pts_within_radius(board, start, search_rad)
    scores = []
    for c in nearby_pts:
        if c == start or c == end:
            continue
        path1 = L_connecting_two_pos(start, c)
        path2 = L_connecting_two_pos(c, end)
        combines = path1.get_segments() + path2.get_segments()
        path = path_class.Path(combines)
        pts = path.get_coords(board)
        if contains_unwanted_shipyard(board, path, shipyards):
            continue

        scores.append((len(pts), path))
    scores = sorted(scores, key=lambda x: x[0])

    return scores[0][1]





def find_min_dist_pts(board, pt, pts):
    min_d = board.configuration.size
    min_pt = None
    for p in pts:
        d = manhattan_distance(board, pt, p)
        if d < min_d:
            min_d = d
            min_pt = p
    return min_d, min_pt


def closest_approach_fleet(board, pt, fleets, radius):
    m_dist = board.configuration.size
    m_size = 999
    m_f = None
    m_pt = None
    for f in fleets:
        if manhattan_distance(board, pt, f.position) > radius:
            continue
        fpts = get_pts_on_fleets_path(board, f)
        d, closest_pt = find_min_dist_pts(board, pt, fpts)
        if d < m_dist:
            m_dist = d
            m_f = f
            m_size = f.ship_count
            m_pt = closest_pt
    return m_f, m_pt, m_size


def steps_for_fleet_to_reach_pt(board, f, pt):
    fpts = get_pts_on_fleets_path(board, f)
    steps = 1

    for p in fpts:
        if p != pt:
            steps += 1
        else:
            break
    return steps


def get_snipe_path(start, target):
    path1 = L_connecting_two_pos(start, target)
    p1_segs = path1.get_segments()
    path2 = L_connecting_two_pos(target, start)
    p2_segs = path2.get_segments()

    plan = ""
    for s in p1_segs:
        plan += s.get_segment()
    for s in p2_segs:
        plan += s.get_segment()

    if plan[-1].isdigit():
        plan = plan[:-1]

    return plan


def get_center_mass_player(player):
    if len(player.fleets) == 0:
        return kf.Point(20, 20)
    x_running = 0
    y_running = 0
    total = 0
    for f in player.fleets:
        pos = f.position
        count = f.ship_count

        x_running += count * pos[0]
        y_running += count * pos[1]
        total += 1

    for s in player.shipyards:
        pos = s.position
        count = s.ship_count
        x_running += count * pos[0]
        y_running += count * pos[1]
        total += 1

    if total == 0:
        return 0, 0
    return x_running / total, y_running / total


def kore_in_cargo(fleets):
    total = 0
    for f in fleets:
        total += f.kore
    return total

def load_turns_from_replay_json(path_to_json):
    with open(path_to_json, 'r') as f:
        match = json.load(f)

    envs = []
    for turn_idx, match_state in enumerate(match["steps"]):
        for player_id in [0,1]:
            match_state[player_id]["observation"]["remainingOverageTime"] \
                = max(0, match_state[player_id]["observation"]["remainingOverageTime"])
        env = kaggle_environments.make("kore_fleets", steps=[match_state],
                                       configuration=match['configuration'])
        envs.append(env)

    return envs
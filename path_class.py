import parameters
import sutils
import kaggle_environments.envs.kore_fleets.helpers as kf
import numpy as np


print(f"{__name__} {parameters.VERSION}")

ALL_DIRECTIONS = {"N", "E", "S", "W"}
ALL_ACTIONS = {"N", "E", "S", "W", "C"}

ACTION_TO_OPPOSITE_ACTION = {
    "N": "S",
    "E": "W",
    "S": "N",
    "W": "E",
}

DIR_MAP = {
    'N': kf.Point(0, 1),
    'S': kf.Point(0, -1),
    'E': kf.Point(1, 0),
    'W': kf.Point(-1, 0)
}


class PathSegment:
    # This class uses the assumption that N 1 means ONE step north. N 0 is same as N 1
    def __init__(self, start, direction, num_steps):
        if num_steps == 0:
            num_steps = 1
        self.start = start
        self.direction = direction
        self.num_steps = num_steps
        if self.num_steps > 1:
            self.segment = self.direction + str(self.num_steps - 1)
        else:
            self.segment = self.direction

    def get_path_coords(self, board):
        positions = [self.start]
        for _ in range(self.num_steps):
            next_position = positions[-1].translate(DIR_MAP[self.direction], board.configuration.size)
            positions.append(next_position)
        return positions[1:]

    def get_start(self):
        return self.start

    def get_end(self, board):
        end = self.get_path_coords(board)[-1]
        return end

    def get_segment(self):
        return self.segment

    def get_direction(self):
        return self.direction

    def get_length(self):
        return self.num_steps

    def unit_test_path(self, board, start, direction, end, length, seg_coords):
        if self.get_start() != start:
            print("start test failed")
        if self.get_direction() != direction:
            print("direction test failed")
        if self.get_length() != length:
            if self.get_length() != 1 and length == 0:
                print(f"length test failed. length {length}, get_length {self.get_length()}")

        if self.get_end(board) != end:
            print(f"end test failed. end {end} get_end {self.get_end(board)}")
        path_coords = self.get_path_coords(board)
        if len(path_coords) != len(seg_coords):
            print("test failed, different coord lengths")
        for i in range(len(seg_coords)):
            if seg_coords[i] != path_coords[i]:
                print("Coords test failed")
                break
        return self.get_path_coords(board)


class Path:
    def __init__(self, path_segments):

        self.paths = path_segments
        if len(path_segments) > 1:
            self.simplify()

    def get_segments(self):
        return self.paths

    def simplify(self):
        temp = self.paths[1:]
        self.paths = [self.paths[0]]

        for p in temp:
            self.add_to(p)

    def add_to(self, path):
        prev = self.paths[-1]
        prev_direction = prev.get_direction()
        prev_length = prev.get_length()
        if prev_direction == path.get_direction():
            new_segment = PathSegment(prev.get_start(), prev_direction, prev_length + path.get_length())
            self.paths[-1] = new_segment
        else:
            self.paths.append(path)

    def get_raw_path(self):

        path = []

        for p in self.paths:
            path.append(p.get_segment())
            return "".join(path)

    def get_compact_path(self):
        path = []
        for i in range(len(self.paths) - 1):
            path.append(self.paths[i].get_segment())
        path = ''.join(path)
        path += self.paths[-1].get_direction()

        return path

    def get_coords(self, board):
        coords = []
        for seg in self.paths:
            seg_coords = seg.get_path_coords(board)
            if len(coords) > 0 and coords[-1] == seg_coords[0]:
                coords += seg_coords[1:]
            else:
                coords += seg_coords
        return coords

    def coords_to_numpy(self, board):
        z = np.zeros((21, 21))
        positions = self.get_coords(board)
        if len(positions) == 0:
            return z
        step = 0
        for i in range(len(positions)):
            p = positions[i]
            step += 1
            if z[p[0], p[1]] >= 1:
                z[p[0], p[1]] += .9 * sutils.KORE_REGEN_FACTOR[step]
            else:
                z[p[0], p[1]] += 1 * sutils.KORE_REGEN_FACTOR[step]


        return z / len(positions)


    def unit_test(self, board, coords):
        path_coords = self.get_coords(board)
        if len(path_coords) != len(coords):
            print("test failed, different coord lengths")
        for i in range(len(coords)):
            if coords[i] != path_coords[i]:
                print("Coords test failed")
                break


# this is for converting flight plans to coordinates
# r is a flight plan that maybe partial
# if r begins with a number then the direciton is needed
class Route:
    def __init__(self, d, r, start):

        self.start = start
        self.route = r
        self.tokens = []
        self.dir = d
        self.tokenize()

        if len(self.tokens) > 0 and self.tokens[0].isdigit():
            self.add_dir()
        elif len(self.tokens) == 0:
            self.tokens = [d]
        self.route = "".join(self.tokens)

    def add_dir(self):
        self.tokens[0] = str(int(self.tokens[0]) - 1)
        if self.tokens[0] == '0' or self.tokens[0] == '-1':
            self.tokens = self.tokens[1:]
        self.tokens = [self.dir] + self.tokens

        if self.tokens[0].isdigit():
            print("Error in add_dir tokens[0] should not be 0")

    def tokenize(self):
        self.tokens = []
        buffer = ''
        for c in self.route:
            if c.isdigit():
                buffer += c
            else:
                if buffer:
                    self.tokens.append(buffer)
                    buffer = ''
                if c in "NESWC":
                    self.tokens.append(c)
        if buffer:
            self.tokens.append(buffer)

    def pts(self, board):
        positions = []
        start = self.start
        positions.append(start)
        prev = self.tokens[0]

        if prev.isdigit():
            print("horror")
        for a in self.tokens:
            if a == "C":
                return positions, True
            if a.isdigit():
                count = int(a)
                for _ in range(count):
                    next_position = positions[-1].translate(DIR_MAP[prev], board.configuration.size)
                    positions.append(next_position)
            else:
                next_position = positions[-1].translate(DIR_MAP[a], board.configuration.size)
                positions.append(next_position)
                prev = a
        return positions[1:], False

import path_class
import kaggle_environments.envs.kore_fleets.helpers as kf

import sutils


def unit_test_pathsegment(board):
    direction = "S"
    start = kf.Point(0, 0)
    length = 5

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(0, 20), kf.Point(0, 19), kf.Point(0, 18), kf.Point(0, 17), kf.Point(0, 16)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(0, 16), length, seg_coords)
    print(coords)

    direction = "N"
    start = kf.Point(0, 0)
    length = 0

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(0, 1)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(0, 1), length, seg_coords)
    print(coords)

    direction = "N"
    start = kf.Point(0, 0)
    length = 1

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(0, 1)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(0, 1), length, seg_coords)
    print(coords)

    direction = "E"
    start = kf.Point(0, 0)
    length = 0

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(1, 0)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(1, 0), length, seg_coords)
    print(coords)

    direction = "E"
    start = kf.Point(0, 0)
    length = 1

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(1, 0)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(1, 0), length, seg_coords)
    print(coords)

    direction = "W"
    start = kf.Point(0, 0)
    length = 1

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(20, 0)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(20, 0), length, seg_coords)
    print(coords)

    direction = "W"
    start = kf.Point(0, 0)
    length = 5

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(20, 0), kf.Point(19, 0), kf.Point(18, 0), kf.Point(17, 0), kf.Point(16, 0)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(16, 0), length, seg_coords)
    print(coords)

    direction = "W"
    start = kf.Point(15, 5)
    length = 5

    seg = path_class.PathSegment(start, direction, length)
    seg_coords = [kf.Point(14, 5), kf.Point(13, 5), kf.Point(12, 5), kf.Point(11, 5), kf.Point(10, 5)]
    coords = seg.unit_test_path(board, start, direction, kf.Point(10, 5), length, seg_coords)
    print(coords)


    print("PathSegment test done")
    exit()

def unit_test_path(board):

    direction = "W"
    start = kf.Point(15, 5)
    length = 5
    seg1 = path_class.PathSegment(start, direction, length)

    direction = "S"
    start = kf.Point(10, 5)
    length = 5
    seg2 = path_class.PathSegment(start, direction, length)

    path = path_class.Path([seg1, seg2])

    coords = seg1.get_path_coords(board) + seg2.get_path_coords(board)

    path.unit_test(board, coords)

    exit()

def test_amount_of_kore_in_n_turns(predictions, actual):

    preds = []

    for i in range(1, len(predictions)):
        preds.append(predictions[i]-predictions[i-1])

    print(preds)
    for k, v in actual.items():
        if "gain" in actual[k]:
            print(k, actual[k]["gain"])






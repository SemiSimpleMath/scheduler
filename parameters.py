import kaggle_environments.envs.kore_fleets.helpers as kf
expo_locations_p0 = [kf.Point(7, 11), kf.Point(4, 12), kf.Point(8, 16)]  # , kf.Point(3, 9), kf.Point(3, 18)]
expo_locations_p1 = [kf.Point(13, 8), kf.Point(17, 8), kf.Point(9, 4)]  # , kf.Point(12, 3), kf.Point(16, 11), kf.Point(15, 10)]

USE_EXPO_LOCATIONS = True

SPAWN_MAX_DEFENSE_PRIORITY = -9
UNSTOPPABLE_ATTACK_PRIORITY = -8.5
ATTACK_PRIORITY = -5
AVALANCHE_ATTACK_PRIORITY = -7
EXPO_PRIORITY = -6
DEFEND_PRIORITY = -9
SHORT_DISTANCE_ATTACK_PRIORITY = -8
SNIPE_PRIORITY = -4.5
REINFORCE_PRIORITY = -4.4
ROUND_TRIP_PRIORITY = -4
SPAWN_PRIORITY = -3
LAY_IN_WAIT_PRIORITY = -4.5
lay_in_wait_radius = 7
risk1 = 1.1 # Multiplier for enemy ship size medium when risk is 1
risk2 = 1.1 # Multiplier for enemy ships when risk is >= 2
hopeless_attack_parameter = 7
# good number so far 2,3,5?
WAIT_STEPS = 5 # How long to wait if you don't have perfect send amount
CLOSEST_SHIPYARD = 4 # new expo locations  CLOSEST_SHIPYARD <= dist <= FURTHEST_SHIPYARD
FURTHEST_SHIPYARD = 10
attack_random_param = .7
# good numbers so far 5,2
paths_overlap_param1 = 5 # num of points that two paths can share before they are considered to overlap
paths_overlap_param2 = 1 # num of fleets that are allowed to overlap


MAX_WAIT_TIME_TO_EXPO = 20
USE_SY_PATHS = False
VERSION = 1.41

print(f"{__name__} {VERSION}")
import copy
import sutils
class KoreManager:
    def __init__(self, board, config):
        self.board = copy.deepcopy(board)
        self.config = copy.deepcopy(config)
        self.turn_start_kore = None
        self.amount_spent_this_turn = None
        if board is not None:
            self.me = board.current_player
            self.kore = self.me.kore
            self.spawn_cost = board.configuration.spawn_cost
        else:
            self.me = None
            self.kore = None
            self.spawn_cost = None
        self.kore_left = self.kore
        self.estimated_kore_rate = 0

    def update(self, board):
        self.me = board.current_player
        self.board = copy.deepcopy(board)
        self.kore = self.me.kore
        self.kore_left = self.kore
        self.turn_start_kore = self.me.kore
        self.amount_spent_this_turn = 0
        self.spawn_cost = board.configuration.spawn_cost

    def get_kore_left(self):
        # this is the kore left that has been unallocated for this turn
        return self.kore

    def get_estimated_kore_rate(self):
        return self.estimated_kore_rate

    def most_can_spend(self):
        ms = 0
        for s in self.me.shipyards:
            ms += s.max_spawn
        return self.spawn_cost * ms

    def update_kore(self, amount):
        self.kore_left += amount
        self.amount_spent_this_turn += amount



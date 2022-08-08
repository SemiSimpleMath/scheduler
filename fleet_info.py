class FleetInfo:
    def __init__(self):
        self.enemy_attacking_fleets = {}
        return

    def update(self, board):
        me = board.current_player
        players = board.players
        enemy = None
        for key, p in players.items():
            if p.id != me.id:
                enemy = p
        enemy_fleets = enemy.fleets

        enemy_fleet_ids = []
        for e in enemy_fleets:
            enemy_fleet_ids.append(e.id)
        pop_these = []
        for f in self.enemy_attacking_fleets:
            if f not in enemy_fleet_ids:
                pop_these.append(f)

        for s_id in pop_these:
            self.enemy_attacking_fleets.pop(s_id)
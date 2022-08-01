import json
import main


FROM, TO = 245, 260       # Replay steps range
PLAYER = 0                  # Player number
FILE="./replays/chad_loss_5.json"

with open(FILE, "r") as cin:
    f = cin.read()


r = json.loads(f)

env = r.get('environment', r)

conf = env['configuration']
agent = main.agent
for step in range(FROM, TO+1):
    obs = env['steps'][step][0]['observation']
    obs["player"] = PLAYER

    actions = agent(obs, conf)

    print(f'{step}: {actions}')
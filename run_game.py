import agents
import main
import json
import kaggle_environments.envs.kore_fleets.helpers as kf
from kaggle_environments import make

import sys
print(sys.argv)
run_num = sys.argv[-1]
beta_chad = agents.beta_chad.main.agent
jjj = agents.beta_chad.main.agent

agent1 = main.agent
env = make("kore_fleets", debug=True)
print(env.name, env.version)

env.reset(2)
#opponent = beta_chad
opponent = jjj
env.run([agent1, opponent])

final_state = env.steps[-1]

s1, s2 = final_state

if s1.reward > s2.reward:

    print("0")
    episode = env.render(mode="json")
    j = env.toJSON()
    with open(f'./replays/chad_win_{run_num}.json', 'w') as f:
        json.dump(j, f)
else:
    print("1")

    episode = env.render(mode="json")
    j = env.toJSON()

    with open(f'./replays/chad_loss_{run_num}.json', 'w') as f:
        json.dump(j, f)
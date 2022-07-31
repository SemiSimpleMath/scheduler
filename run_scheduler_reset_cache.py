import agents
import main
import json
import kaggle_environments.envs.kore_fleets.helpers as kf
from kaggle_environments import make
import parameters
from collections import defaultdict

beta_chad = agents.beta_chad.main.agent
num_games = 1
agent1 = main.agent
env = make("kore_fleets", debug=True)
print(env.name, env.version)
results = defaultdict(int)
for run_num in range(0, num_games):
    env.reset(2)
    opponent = beta_chad
    env.run([agent1, opponent])

    final_state = env.steps[-1]

    s1, s2 = final_state

    if s1.reward > s2.reward:

        print("0")
        results[0]+=1
        episode = env.render(mode="json")
        j = env.toJSON()
        with open(f'./replays/chad_win_{run_num}.json', 'w') as f:
            json.dump(j, f)
    else:
        print("1")
        results[1] += 1
        episode = env.render(mode="json")
        j = env.toJSON()

        with open(f'./replays/chad_loss_{run_num}.json', 'w') as f:
            json.dump(j, f)

    print(results)
    main.player = None
    main.cache = None

    parameters.expo_locations_p0 = [kf.Point(7, 11), kf.Point(4, 12), kf.Point(8, 16)]  # , kf.Point(3, 9), kf.Point(3, 18)]
    parameters.expo_locations_p1 = [kf.Point(13, 8), kf.Point(17, 8), kf.Point(9, 4)]  # , kf.Point(12, 3), kf.Point(16, 11), kf.Point(15, 10)]
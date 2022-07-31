
import subprocess
num_games = 100


from collections import defaultdict
results = defaultdict(int)
for i in range(0,num_games):
    output = subprocess.check_output(['python', 'run_game.py', str(i)])
    output=str(output,'utf-8')
    output = output.strip()
    print(output)

    results[output[-1]] += 1
    print(results)




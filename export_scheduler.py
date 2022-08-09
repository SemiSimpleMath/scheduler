import shutil
import parameters
import os
version = str(parameters.VERSION)
version = version.split(".")
version = "".join(version)

dest = f"agents//sched_{version}"
os.makedirs(os.path.join(dest), exist_ok=True)

def copy_file(src, dest, version, imports):
    with open(src) as f:
        lines = f.readlines()

    with open(dest, "w") as f:
        for i, imp in enumerate(imports):
            imp = f"from . import {imp}_{version} as {imp}"
            lines[i] = imp

        f.write("\n".join(lines))

src = "./main.py"
dest = f"./agents/sched_{version}/" + src
imports = ["shipyardmanager", "parameters", "fleet_info", "sutils"]
copy_file(src, dest, version, imports)


src = "./parameters.py"
src_v = f"parameters_{version}.py"
dest = f"./agents/sched_{version}/" + src_v
shutil.copyfile(src, dest)

src = "./path_class.py"
src_v = f"path_class_{version}.py"
imports = ["parameters", "sutils"]
dest = f"./agents/sched_{version}/" + src_v
copy_file(src, dest, version, imports)

src = "./shipyardmanager.py"
src_v = f"shipyardmanager_{version}.py"
imports = ["fleet_info", "sutils", "shipyard", "parameters"]
dest = f"./agents/sched_{version}/" + src_v
copy_file(src, dest, version, imports)

src = "./shipyard.py"
src_v = f"shipyard_{version}.py"
imports = ["sutils", "parameters"]
dest = f"./agents/sched_{version}/" + src_v
copy_file(src, dest, version, imports)

src = "./sutils.py"
src_v = f"sutils_{version}.py"
imports = ["path_class", "parameters"]
dest = f"./agents/sched_{version}/" + src_v
copy_file(src, dest, version, imports)

src = "./fleet_info.py"
src_v = f"fleet_info_{version}.py"
dest = f"./agents/sched_{version}/" + src_v
shutil.copyfile(src, dest)

src = "./__init__.py"
dest = f"./agents/sched_{version}/" + src
shutil.copyfile(src, dest)



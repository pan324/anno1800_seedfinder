"""
Copy pngs into a single folder.
The game files must already be extracted with RDAExplorer.
"""

import sys,os, shutil
from PIL import Image


root = "../data"  # Path to all extracted files.
outdir = "pics"

####

try: os.makedirs(outdir)
except FileExistsError: pass

def Walks():
    yield os.walk(root+"/sessions/islands/pool")
    for dirname in os.listdir(root):
        if dirname.startswith("dlc"):
            yield os.walk(root+"/"+dirname+"/sessions")


found = {}
for walk in Walks():
    for dir0, dirs, fnames in walk:
        for fname in fnames:
            if fname != "gamemapimage.png": continue
            path = (dir0+"/"+fname).replace("\\","/")
            newname = path.split("/")[-2]

            assert newname not in found
            found[newname] = path

for name,path in found.items():
    # Make them smaller to keep the repository smallish.
    NORM = 2
    im = Image.open(path)
    im = im.resize((int(im.width/NORM), int(im.height/NORM)))
    im.save(outdir+"/"+name+".png")
##    shutil.copy2(path, outdir+"/"+name+".png")



# NPC pictures:
for name in ["02","08","07", "03", "04", "05"]:
    NORM = 1.4
    path = f"{root}/ui/2kimages/main/profiles/3rd_party_{name}_0.dds"
    im = Image.open(path)
    im = im.resize((int(im.width/NORM), int(im.height/NORM)))
    im.save(f"{outdir}/NPC_{name}.png")
##    shutil.copy2(path, f"{outdir}/NPC_{name}.dds")
























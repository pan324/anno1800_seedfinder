"""
Run over all map template (.a7tinfo) files and turn them into csv.
The game files must already be extracted with RDAExplorer.
"""

import sys,os,zlib, shutil
from binascii import hexlify, unhexlify
from struct import pack,unpack
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt


root = "../data"  # Path to all extracted files.
outdir = "maps"


def CreateXmls():
    try: os.makedirs(outdir)
    except FileExistsError: pass

    def Walks():
        yield os.walk(root+"/sessions/maps")
        for dirname in os.listdir(root):
            if dirname.startswith("dlc"):
                yield os.walk(root+"/"+dirname+"/sessions")


    found = {}
    for walk in Walks():
        for dir0, dirs, fnames in walk:
            for fname in fnames:
                if not fname.endswith(".a7tinfo"): continue
    
                path = (dir0+"/"+fname).replace("\\","/")
                newname = path.split("/")[-2]

                assert newname not in found
                found[newname] = path
    
    for name,path in found.items():
        cmd = os.path.normpath(r"../FileDBReader/FileDBReader.exe decompress -y -f "+path)
        rv = os.system(cmd)
        if rv:
            raise Exception("Could not run cmd. FileDBReader not found?")
        
        # No output directory is possible, so move them manually.
        os.rename(path.replace(".a7tinfo",".xml"), outdir+"/"+name+".xml")


def IsEmpty(node):
    return node.text is None and not list(node.items())
    
class Map:
    def __repr__(self):
        return f"{self.name}    xy:{self.xy}, playable:{self.playable}\n{self.df}"

class Stub: 1

def Unpack(fmt, parent, nodename):
    """Streamlined unpacking by node name."""
    data = parent.find(nodename)
    if data is None: return "None"
    return unpack(fmt, unhexlify(data.text))





##CreateXmls()



maps = {}
for fname in os.listdir(outdir):
    if not fname.endswith(".xml"): continue
    tree = ET.parse(outdir+"/"+fname)
    root = tree.getroot()

    mp = root[0]
    obj = Map()

    assert set([elem.tag for elem in mp]) == {'TemplateElement', 'RandomlyPlacedThirdParties', 'Size', 'PlayableArea', 'ElementCount'}

    # General map info:
    obj.name = fname
    obj.xy = Unpack("II", mp, "Size")
    obj.playable = Unpack("IIII", mp, "PlayableArea")
    obj.count = Unpack("I", mp, "ElementCount")[0]

    assert obj.xy[0] == obj.xy[1]
##    assert obj.playable[0] == obj.playable[1]
##    assert obj.playable[2] == obj.playable[3]
    assert IsEmpty(mp.find("RandomlyPlacedThirdParties"))


    # The actual island slots:
    elems = mp.findall("TemplateElement")
    assert len(elems) == obj.count
    slots = []
    for entry in elems:
        slot = Stub()
        assert entry.find("Element")
        if entry.find("ElementType") is None:
            slot.type = None
        else:
            slot.type = Unpack("I",entry,"ElementType")[0]

        entry = entry.find("Element")
        slot.x,slot.y = Unpack("II", entry, "Position")
        slot.size = Unpack("H", entry, "Size") 
        if slot.size == "None": slot.size = 0
        else: slot.size = slot.size[0]
        slot.sz = slot.size  # To avoid collision with pd Dataframe later on.

        # Diff is not really used by island slots.
        # It is defined by islands instead.
        diff = entry.find("Difficulty")
        if diff is not None:
            assert IsEmpty(diff)

        # Finally grab the slot.id.
        entry = entry.find("Config")
        if entry is not None:
            diff = entry.find("Difficulty")
            if diff is not None:
                assert diff.text is None

            typ = entry.find("Type")
            ids = list(typ.findall("id"))
            assert len(ids)<=1
            
            if len(ids)==1:
                slot.id = Unpack("H",typ, "id")[0]
            else:
                slot.id = 0
        else:
            slot.id = 0

        slots.append(slot)


    # To dataframe.
    kwords = ["x","y","type","id","sz"]
    d = {k:[] for k in kwords}
    for kword in kwords:
        for slot in slots:
            d[kword].append(getattr(slot, kword))

    df = pd.DataFrame(d)
    df.index = range(len(df))
    df[df.isna()] = 0
    df = df.astype(int)
        
    obj.df = df
    maps[obj.name] = obj


import pickle


for name,obj in maps.items():
    

    
####    pickle.dump)
##    if name == "moderate_snowflake_ll_01.xml":
##        print(obj)
######    print(obj)
######    assert (obj.playable[0] <= obj.df.x).all()
######    assert (obj.playable[1] <= obj.df.y).all()
####    print(obj)
####    print(name, obj.df.x.min(), obj.df.x.max(), obj.xy)
####    counts = dict(obj.df.groupby("sz").sz.count())
##
##    df = obj.df
##    print(name, df.x.min(), df.x.max(), df.y.min(), df.y.max()) 
####    count = obj.df.value_counts("sz")
####    if count.get(2,0) >= 8:
####        print(name, count)
##    
    
##    1
    # We only care about the slots and not the full map though.
    obj.df.to_csv(outdir+"/"+obj.name.replace(".xml",".csv"), index=False)
    










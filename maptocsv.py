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
import pickle


root = ".."  # Path to all extracted files.
outdir = "maps"


# Use the templates/templates.csv to traverse all a7tinfo files.
templates = pd.read_csv("templates/templates.csv")
paths = list(templates.TemplateFilename) + list(templates.EnlargedTemplateFilename[~templates.EnlargedTemplateFilename.isna()])

def CreateXmls():
    """Convert a7tinfo files into xml files, placed next to them."""
    try: os.makedirs(outdir)
    except FileExistsError: pass
    for path in paths:  # Path to .a7t files.
        print(path)
        path = root+"/"+path+"info"
        cmd = os.path.normpath(r"../FileDBReader/FileDBReader.exe decompress -y -f "+path)
        rv = os.system(cmd)
        if rv:
            raise Exception("Could not run cmd. FileDBReader not found?")

def IsEmpty(node):
    return node.text is None and not list(node.items())
    
class Map:
    def __repr__(self):
        return f"{self.path}    xy:{self.xy}, playable:{self.playable}\n{self.df}"

class Stub: 1

def Unpack(fmt, parent, nodename):
    """Streamlined unpacking by node name."""
    data = parent.find(nodename)
    if data is None: return "None"
    return unpack(fmt, unhexlify(data.text))




CreateXmls()


maps = {}
for path in paths:
    print(path)
    
    tree = ET.parse(root+"/"+path[:-4]+".xml")
    mp = tree.getroot()[0]
    obj = Map()

    # Additional tags for initial playable area and (redundantly with template) whether it gets larger or not.
    if not {elem.tag for elem in mp} == {'TemplateElement', 'RandomlyPlacedThirdParties', 'Size', 'PlayableArea', 'ElementCount'}:
        print("  ",{elem.tag for elem in mp}-{'TemplateElement', 'RandomlyPlacedThirdParties', 'Size', 'PlayableArea', 'ElementCount'})

    # General map info:
    obj.path = path
    obj.xy = Unpack("II", mp, "Size")
    obj.playable = Unpack("IIII", mp, "PlayableArea")
    obj.count = Unpack("I", mp, "ElementCount")[0]

    assert obj.xy[0] == obj.xy[1]
##    assert obj.playable[0] == obj.playable[1]
##    assert obj.playable[2] == obj.playable[3]
    if not IsEmpty(mp.find("RandomlyPlacedThirdParties")):
        print("  ",mp.find("RandomlyPlacedThirdParties"))


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
    maps[obj.path] = obj




# Put the data used by the code into the pickle but keep a text log so we can see what is going on.
pickle.dump({k:v.df for k,v in maps.items()}, open(outdir+"/pickle","wb"))
with open(outdir+"/picklelog.txt","w") as f2:
    for name,obj in maps.items():
        f2.write(repr(obj)+"\n")
    






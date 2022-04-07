"""
Load map templates from the assets.xml.
"""

import sys,os,zlib, shutil
from binascii import hexlify, unhexlify
from struct import pack,unpack
import pandas as pd
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from io import StringIO


root = "../data"  # Path to all extracted files.


ASSET_PATH = root+"/config/export/main/asset/assets.xml"




pd.options.display.max_colwidth = 100
pd.options.display.width  = 0
pd.options.display.max_rows = 120


def Fillnan(df):
    mask = df.dtypes==object
##    df.loc[:,mask] = df.loc[:,mask].fillna("")
    df.loc[:,~mask] = df.loc[:,~mask].fillna(0)
def Clean(df):
    """Replace Nan by 0 if possible.
       Simplify the dtypes if possible.
       Remove cols with only identical vals.
    """
    Fillnan(df)
    df = df.convert_dtypes()
    return df[df.columns[df.nunique() > 1]]



def TemplatesToCsv():
    df = pd.read_xml(ASSET_PATH, xpath=".//MapTemplate").dropna(axis=1,how="all")
    df = df[~df.TemplateFilename.isna()]
    df = df[~df.TemplateRegion.isna()]
    df = Clean(df)
    df.TemplateSize.fillna("Small", inplace=True)
    df.set_index("TemplateFilename", inplace=True)

    try: os.mkdir("templates")
    except: pass
    df.to_csv("templates/templates.csv")


TemplatesToCsv()















# The game internally keeps 5 separate lists of islands, so at the end we want 5 csv files.
# That separation is not encoded as an island field but rather more directly through the XML structure.
# So we need to expand the xpath to go some levels back.
# Fromt there we can iterate over the 5 children and feed them to pandas.
# But that does not apply to DLCs which do whatever.
# So there is something else. 
# The assets.xml also has the following:
#   <IslandSizes>
#   <Small>
#     <MaxWidth>192</MaxWidth>
#     <MaxHeight>192</MaxHeight>
#   </Small>
#   <Medium>
#     <MaxWidth>272</MaxWidth>
#     <MaxHeight>272</MaxHeight>
#   </Medium>
#   <Large>
#     <MaxWidth>384</MaxWidth>
#     <MaxHeight>384</MaxHeight>
#   </Large>
# Some medium islands have 320 according to the .a7me, which is too large for Medium.
# But we can grab the ActiveMapRect from the .a7info and subtract xmax-xmin and ymax-ymin and that seems to work.
#
# But the island order is all over the place!
# Apparently the correct order is to traverse the file from bottom to top in order to find groups.
# But once a group is found, everything inside that group goes in normal top-to-bottom order.
# Anyway, this is way too risky versus just using the stuff that x64 dumped.
# 
##assets = ET.parse("assets.xml")
##node = assets.getroot()
##labels = ["small","medium","large","decor","npc"]
##dfss = [[] for i in range(len(labels))]
##for groups in node.findall(".//RandomIsland/../../../../.."):
##    print(groups)
##    for i,group in enumerate(groups):
##        print(i)
##        # Now feed that group back into pandas.
##        dfss[i].append(pd.read_xml(StringIO(ET.tostring(group).decode()), xpath=".//RandomIsland")) 
##for label,dfs in zip(labels, dfss):
##    df = pd.concat(dfs).set_index("FilePath")
##    print(df)






##def CreateAssetExcerpt():
##    """Make copy of relevant data (non-DLC only) on disk for faster debugging."""
##    assets = ET.parse(root+"/config/export/main/asset/assets.xml")
##    for node in assets.iter():
##        assert not node.attrib
##        assert node.tail is None or not node.tail.strip()
##    # => No attribs. No tails.
##    node = assets.getroot()
##    s = node[0][4][0][5]
##    open("assets.xml","wb").write(ET.tostring(s))
##
##CreateAssetExcerpt()



# Rough overview:
#   Groups:
#     Mineslots data
#     Fertilities data
#     RandomIsland data:
#       IslandDifficulty: Normal;Hard
#       IslandType: Normal;Starter
#       IslandRegion: Moderate
#       FilePath: Path to the .a7m file.
#       IslandBaseName: Only the name and without _river.
#    MapTemplate data:
#












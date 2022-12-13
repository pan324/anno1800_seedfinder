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



















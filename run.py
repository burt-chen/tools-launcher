"""Launcher 進入點。"""

# ── 啟動硬化 + 標準庫打包(self-heal / 動態載入工具相依)──────────
# 兩個目的:
# 1) PyInstaller 只會打包它「靜態分析得到」的 import。launcher 動態載入
#    的工具(如 fontTools / matplotlib / ezdxf)會用到 launcher 本身沒用到
#    的標準庫,若不在此明確 import,凍結後工具會 ModuleNotFoundError
#    (例:No module named 'html' / 'timeit')。這裡用「明確 import 陳述式」
#    讓 PyInstaller 一併打包。
# 2) onefile 自我更新後,新行程可能沿用舊 _MEIxxxx 暫存夾,舊行程結束
#    即被刪;先在啟動最早期把這些模組載入記憶體,之後就不會再去
#    base_library.zip 找而失敗。
#
# 注意:必須是「明確 import」,不能用 importlib.import_module(變數),
# 否則 PyInstaller 靜態分析看不到、不會打包。
import abc                 # noqa: F401
import argparse            # noqa: F401
import array               # noqa: F401
import ast                 # noqa: F401
import base64              # noqa: F401
import binascii            # noqa: F401
import bisect              # noqa: F401
import bz2                 # noqa: F401
import calendar            # noqa: F401
import codecs              # noqa: F401
import collections.abc     # noqa: F401
import configparser        # noqa: F401
import contextlib          # noqa: F401
import copy                # noqa: F401
import copyreg             # noqa: F401
import csv                 # noqa: F401
import ctypes              # noqa: F401
import ctypes.util         # noqa: F401
import dataclasses         # noqa: F401
import datetime            # noqa: F401
import decimal             # noqa: F401
import difflib             # noqa: F401
import dis                 # noqa: F401
import doctest             # noqa: F401
import email.feedparser    # noqa: F401
import email.header        # noqa: F401
import email.message       # noqa: F401
import email.parser        # noqa: F401
import email.utils         # noqa: F401
import encodings.idna      # noqa: F401
import enum                # noqa: F401
import fnmatch             # noqa: F401
import fractions           # noqa: F401
import functools           # noqa: F401
import gc                  # noqa: F401
import getpass             # noqa: F401
import gettext             # noqa: F401
import glob                # noqa: F401
import gzip                # noqa: F401
import hashlib             # noqa: F401
import heapq               # noqa: F401
import hmac                # noqa: F401
import html                # noqa: F401
import html.entities       # noqa: F401
import html.parser         # noqa: F401
import http.client         # noqa: F401
import http.cookies        # noqa: F401
import importlib.metadata  # noqa: F401
import importlib.resources # noqa: F401
import importlib.util      # noqa: F401
import inspect             # noqa: F401
import io                  # noqa: F401
import itertools           # noqa: F401
import json                # noqa: F401
import linecache           # noqa: F401
import locale              # noqa: F401
import logging.config      # noqa: F401
import logging.handlers    # noqa: F401
import lzma                # noqa: F401
import mimetypes           # noqa: F401
import numbers             # noqa: F401
import pickle              # noqa: F401
import pkgutil             # noqa: F401
import platform            # noqa: F401
import plistlib            # noqa: F401
import pprint              # noqa: F401
import queue               # noqa: F401
import random              # noqa: F401
import re                  # noqa: F401
import runpy               # noqa: F401
import secrets             # noqa: F401
import select              # noqa: F401
import shlex               # noqa: F401
import shutil              # noqa: F401
import signal              # noqa: F401
import socket              # noqa: F401
import sqlite3             # noqa: F401
import ssl                 # noqa: F401
import statistics          # noqa: F401
import string              # noqa: F401
import struct              # noqa: F401
import subprocess          # noqa: F401
import tarfile             # noqa: F401
import tempfile            # noqa: F401
import textwrap            # noqa: F401
import threading           # noqa: F401
import timeit              # noqa: F401
import token               # noqa: F401
import tokenize            # noqa: F401
import traceback           # noqa: F401
import types               # noqa: F401
import typing              # noqa: F401
import unicodedata         # noqa: F401
import unittest            # noqa: F401
import urllib.error        # noqa: F401
import urllib.parse        # noqa: F401
import urllib.request      # noqa: F401
import uuid                # noqa: F401
import warnings            # noqa: F401
import weakref             # noqa: F401
import webbrowser          # noqa: F401
import xml.dom.minidom     # noqa: F401
import xml.etree.ElementTree  # noqa: F401
import xml.sax             # noqa: F401
import xmlrpc.client       # noqa: F401
import zipfile             # noqa: F401
import zlib                # noqa: F401
# ──────────────────────────────────────────────────────────────

from app.main import main

if __name__ == "__main__":
    main()

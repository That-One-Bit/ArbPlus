## 00 -- 00_header.py -- header / imports
#!/usr/bin/env python3
"""
ArbPlus Language Interpreter
"A Really Bad Programming Language"

A single-file Python interpreter for the ArbPlus language.
Supports: metadata, declarations, overrides, functions, shell escapes,
inline C, typed variables, arb containers, file I/O, directory ops,
conditionals, loops, colored I/O, OS globals, and extensions.
"""

import sys
import os
import re
import textwrap
import subprocess
import time
import struct
import base64
import json
import datetime
import platform
import shutil
import ctypes
import importlib.util
import urllib.request
import urllib.error
from typing import Any, Optional as Opt
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# DATA TYPE DEFINITIONS
# =============================================================================



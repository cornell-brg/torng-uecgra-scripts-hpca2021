#! /usr/bin/env python
#============================================================================
# dodo
#============================================================================
# Doit file with reporter that outputs task actions as strings.
#
# Date   : April 4, 2015
# Author : Christopher Torng
#

from doit.task import clean_targets
from doit.tools import check_timestamp_unchanged
from doit.tools import create_folder

from doit_utils import *

#----------------------------------------------------------------------------
# Config
#----------------------------------------------------------------------------

DOIT_CONFIG = {'reporter'      : MyReporter,
               'verbosity'     : 2,
               }

#----------------------------------------------------------------------------
# Tasks
#----------------------------------------------------------------------------

from task_explore import *



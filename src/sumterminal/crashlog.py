#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018-2026 William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
import datetime;
import faulthandler;
import os;
from pathlib import Path;
import traceback;


_FAULT_HANDLE=None;


def state_directory(env=None):
    values=os.environ if env is None else env;
    if os.name=="nt":
        root=values.get("LOCALAPPDATA") or str(Path.home()/"AppData"/"Local");
        return Path(root)/"SUM"/"Terminal";
    root=values.get("XDG_STATE_HOME") or str(Path.home()/".local"/"state");
    return Path(root)/"sumterminal";


def crash_log_path(env=None):
    return state_directory(env)/"crash.log";


def _timestamp():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds");


def install_faulthandler(path=None):
    global _FAULT_HANDLE;
    target=Path(path) if path is not None else crash_log_path();
    try:
        target.parent.mkdir(parents=True,exist_ok=True);
        _FAULT_HANDLE=target.open("a",encoding="utf-8",buffering=1);
        _FAULT_HANDLE.write("\n[{}] sumterminal worker start pid={}\n".format(_timestamp(),os.getpid()));
        faulthandler.enable(file=_FAULT_HANDLE,all_threads=True);
    except (OSError,RuntimeError):
        _FAULT_HANDLE=None;
    return target;


def log_message(message,path=None):
    target=Path(path) if path is not None else crash_log_path();
    try:
        target.parent.mkdir(parents=True,exist_ok=True);
        with target.open("a",encoding="utf-8") as handle:
            handle.write("[{}] {}\n".format(_timestamp(),str(message)));
    except OSError:
        pass;
    return target;


def log_exception(context,exc,path=None):
    target=Path(path) if path is not None else crash_log_path();
    try:
        target.parent.mkdir(parents=True,exist_ok=True);
        with target.open("a",encoding="utf-8") as handle:
            handle.write("\n[{}] Python exception in {} pid={}\n".format(_timestamp(),context,os.getpid()));
            traceback.print_exception(type(exc),exc,exc.__traceback__,file=handle);
    except OSError:
        pass;
    return target;

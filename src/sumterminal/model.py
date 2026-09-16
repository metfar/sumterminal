#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
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
from dataclasses import dataclass;
from enum import Enum;
from typing import Optional, Tuple;


class SessionState(str,Enum):
    CREATED="created";
    RUNNING="running";
    EXITED="exited";
    CLOSED="closed";


@dataclass(frozen=True)
class TerminalSize:
    rows: int = 24;
    columns: int = 80;

    def normalized(self):
        return TerminalSize(max(1,int(self.rows)),max(1,int(self.columns)));


@dataclass(frozen=True)
class TerminalEvent:
    kind: str;
    raw: bytes = b"";
    text: str = "";
    exit_code: Optional[int] = None;
    size: Optional[TerminalSize] = None;


@dataclass(frozen=True)
class SessionInfo:
    argv: Tuple[str,...];
    logical_cwd: str;
    native_cwd: str;
    pid: Optional[int];
    state: SessionState;
    size: TerminalSize;

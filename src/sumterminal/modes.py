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


@dataclass
class TerminalModes:
    """Input/output modes negotiated by VT/xterm control sequences.""";

    application_cursor: bool=False;
    application_keypad: bool=False;
    alternate_screen: bool=False;
    cursor_visible: bool=True;
    bracketed_paste: bool=False;
    mouse_tracking: int=0;
    mouse_sgr: bool=False;
    insert_mode: bool=False;
    origin_mode: bool=False;
    autowrap: bool=True;
    keyboard_flags: int=0;

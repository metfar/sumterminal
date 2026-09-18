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
from .config import DropdownPreferences, GeneralPreferences, TerminalPreferences, config_path, load_preferences, save_preferences;
from .decoder import TerminalDecoder;
from .errors import SessionStateError, TerminalError, UnsupportedPlatformError;
from .input import TerminalInputEncoder;
from .modes import TerminalModes;
from .model import SessionInfo, SessionState, TerminalEvent, TerminalSize;
from .screen import Cell, TerminalScreen;
from .session import TerminalSession, default_shell_command;
from .view import HostTerminalView;
from .gui import GuiTerminalView;

__version__="0.1.0a22";
__all__=["Cell","DropdownPreferences","GeneralPreferences","GuiTerminalView","HostTerminalView","SessionInfo","SessionState","SessionStateError","TerminalDecoder","TerminalError","TerminalEvent","TerminalInputEncoder","TerminalModes","TerminalPreferences","TerminalScreen","TerminalSession","TerminalSize","UnsupportedPlatformError","config_path","default_shell_command","load_preferences","save_preferences"];

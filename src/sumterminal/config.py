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
from dataclasses import dataclass, field;
import os;
from pathlib import Path;

from sumkeyboard.hotkeys import normalize_shortcut;


@dataclass
class GeneralPreferences:
    frontend: str="gui";
    shell: str="sumbash";
    theme: str="Dark";
    font_name: str="monospace";
    font_size: int=18;
    font_bold: bool=False;
    font_italic: bool=False;
    font_small_caps: bool=False;


@dataclass
class DropdownPreferences:
    shortcut: str="Ctrl+F12";
    height: int=45;
    width: int=100;
    opacity: float=0.94;
    monitor: str="current";
    position: str="top";
    hide_on_focus_loss: bool=False;
    animation: bool=True;


@dataclass
class TerminalPreferences:
    general: GeneralPreferences=field(default_factory=GeneralPreferences);
    dropdown: DropdownPreferences=field(default_factory=DropdownPreferences);

    def normalized(self):
        self.general.frontend="gui" if str(self.general.frontend).casefold() not in ("gui","host") else str(self.general.frontend).casefold();
        self.general.shell=str(self.general.shell or "sumbash");
        self.general.theme=str(self.general.theme or "Dark");
        self.general.font_name=str(self.general.font_name or "monospace");
        self.general.font_size=max(8,min(72,int(self.general.font_size)));
        self.general.font_bold=bool(self.general.font_bold);
        self.general.font_italic=bool(self.general.font_italic);
        self.general.font_small_caps=bool(self.general.font_small_caps);
        try: self.dropdown.shortcut=normalize_shortcut(self.dropdown.shortcut or "Ctrl+F12");
        except (TypeError,ValueError): self.dropdown.shortcut="Ctrl+F12";
        self.dropdown.height=max(10,min(100,int(self.dropdown.height)));
        self.dropdown.width=max(20,min(100,int(self.dropdown.width)));
        self.dropdown.opacity=max(0.20,min(1.0,float(self.dropdown.opacity)));
        self.dropdown.monitor=str(self.dropdown.monitor or "current");
        self.dropdown.position=str(self.dropdown.position or "top").casefold();
        if self.dropdown.position not in ("top","bottom"): self.dropdown.position="top";
        self.dropdown.hide_on_focus_loss=bool(self.dropdown.hide_on_focus_loss);
        self.dropdown.animation=bool(self.dropdown.animation);
        return self;


def config_path(env=None):
    values=os.environ if env is None else env;
    if os.name=="nt":
        root=values.get("APPDATA") or str(Path.home()/"AppData"/"Roaming");
        return Path(root)/"SUM"/"terminal.toml";
    root=values.get("XDG_CONFIG_HOME") or str(Path.home()/".config");
    return Path(root)/"sum"/"terminal.toml";


def _toml_value(value):
    if isinstance(value,bool): return "true" if value else "false";
    if isinstance(value,float): return "{:.3f}".format(value).rstrip("0").rstrip(".");
    if isinstance(value,int): return str(value);
    text=str(value).replace("\\","\\\\").replace('"','\\"');
    return '"{}"'.format(text);


def _serialize(preferences):
    value=preferences.normalized();
    lines=["[general]","frontend = {}".format(_toml_value(value.general.frontend)),"shell = {}".format(_toml_value(value.general.shell)),"theme = {}".format(_toml_value(value.general.theme)),"font_name = {}".format(_toml_value(value.general.font_name)),"font_size = {}".format(_toml_value(value.general.font_size)),"font_bold = {}".format(_toml_value(value.general.font_bold)),"font_italic = {}".format(_toml_value(value.general.font_italic)),"font_small_caps = {}".format(_toml_value(value.general.font_small_caps)),"","[dropdown]","shortcut = {}".format(_toml_value(value.dropdown.shortcut)),"height = {}".format(_toml_value(value.dropdown.height)),"width = {}".format(_toml_value(value.dropdown.width)),"opacity = {}".format(_toml_value(value.dropdown.opacity)),"monitor = {}".format(_toml_value(value.dropdown.monitor)),"position = {}".format(_toml_value(value.dropdown.position)),"hide_on_focus_loss = {}".format(_toml_value(value.dropdown.hide_on_focus_loss)),"animation = {}".format(_toml_value(value.dropdown.animation)),""];
    return "\n".join(lines);


def save_preferences(preferences,path=None):
    target=Path(path) if path is not None else config_path();
    target.parent.mkdir(parents=True,exist_ok=True);
    target.write_text(_serialize(preferences),encoding="utf-8");
    return target;


def _load_toml(path):
    try:
        import tomllib;
        with Path(path).open("rb") as handle: return tomllib.load(handle);
    except ImportError: pass;
    data={}; section=None;
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line=raw.strip();
        if not line or line.startswith("#"): continue;
        if line.startswith("[") and line.endswith("]"):
            section=line[1:-1].strip(); data.setdefault(section,{}); continue;
        if "=" not in line or section is None: continue;
        key,value=(item.strip() for item in line.split("=",1));
        if value.startswith('"') and value.endswith('"'): value=value[1:-1].replace('\\"','"').replace('\\\\','\\');
        elif value.casefold() in ("true","false"): value=value.casefold()=="true";
        else:
            try: value=float(value) if "." in value else int(value);
            except ValueError: pass;
        data[section][key]=value;
    return data;


def load_preferences(path=None):
    target=Path(path) if path is not None else config_path(); value=TerminalPreferences();
    if not target.exists(): return value.normalized();
    try: data=_load_toml(target);
    except (OSError,ValueError): return value.normalized();
    general=dict(data.get("general",{}) or {}); dropdown=dict(data.get("dropdown",{}) or {});
    for key in ("frontend","shell","theme","font_name","font_size","font_bold","font_italic","font_small_caps"):
        if key in general: setattr(value.general,key,general[key]);
    for key in ("shortcut","height","width","opacity","monitor","position","hide_on_focus_loss","animation"):
        if key in dropdown: setattr(value.dropdown,key,dropdown[key]);
    try: return value.normalized();
    except (TypeError,ValueError): return TerminalPreferences().normalized();

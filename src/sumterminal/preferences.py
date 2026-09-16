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
import shutil;
import os;
import warnings;

from sumkeyboard.hotkeys import install_global_shortcut, normalize_shortcut;

from .config import load_preferences, save_preferences;
from .ipc import send_command;


_ACTION_ID="sumterminal.dropdown";
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT","1");


def toggle_command():
    executable=shutil.which("sumterminal") or "sumterminal";
    return [executable,"--toggle"];


def install_dropdown_shortcut(preferences=None,apply=True):
    value=(preferences or load_preferences()).normalized();
    return install_global_shortcut(_ACTION_ID,value.dropdown.shortcut,toggle_command(),apply=apply);


def show_preferences(preferences=None):
    value=(preferences or load_preferences()).normalized();
    try:
        warnings.filterwarnings("ignore",message=r"Your system is avx2 capable.*",category=RuntimeWarning);
        warnings.filterwarnings("ignore",message=r"pkg_resources is deprecated as an API.*",category=UserWarning);
        import pygame;
        from sumgui.easy import app, button, label, slider, start, window;
        from sumgui.widgets import TextInput;
    except ImportError as exc: raise RuntimeError("sumTerminal preferences require sumGUI/Pygame") from exc;
    current=window("SUM Terminal Preferences",width=760,height=680,base_width=760,base_height=680,theme=value.general.theme,font_name=value.general.font_name,font_size=18);
    class ShortcutInput(TextInput):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs); self.capturing=False; self._before=self.value();
        def handle_event(self,event):
            if event.type==pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                self.capturing=True; self._before=self.value(); self.set_value("Press shortcut..."); self.has_focus=True; return True;
            if self.capturing and event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE: self.set_value(self._before); self.capturing=False; return True;
                modifiers=[];
                if event.mod & pygame.KMOD_CTRL: modifiers.append("Ctrl");
                if event.mod & pygame.KMOD_ALT: modifiers.append("Alt");
                if event.mod & pygame.KMOD_SHIFT: modifiers.append("Shift");
                if event.mod & pygame.KMOD_GUI: modifiers.append("Super");
                key=pygame.key.name(event.key);
                if key.casefold() in ("left ctrl","right ctrl","left alt","right alt","left shift","right shift","left gui","right gui"): return True;
                key=key.upper() if key.casefold().startswith("f") and key[1:].isdigit() else key;
                try: self.set_value(normalize_shortcut("+".join(modifiers+[key])));
                except ValueError: self.set_value(self._before);
                self.capturing=False; return True;
            if self.capturing: return True;
            return super().handle_event(event);
    label("SUM Terminal Preferences",28,18,650,42,font_size=26,bold=True);
    label("Appearance",28,72,650,34,font_size=20,bold=True);
    label("Font",28,116,200,34); font_name=current.add(TextInput(current.rect(270,110,440,42),current.font,text=value.general.font_name,placeholder="monospace / DejaVu Sans Mono / ...",max_length=96,theme=current.theme));
    label("Font size",28,170,200,34); font_size=slider("{} pt".format(value.general.font_size),270,162,440,54,minimum=8,maximum=48,value=value.general.font_size,step=1);
    label("Drop-down",28,232,650,34,font_size=20,bold=True);
    label("Shortcut",28,278,230,34); shortcut=current.add(ShortcutInput(current.rect(270,272,440,42),current.font,text=value.dropdown.shortcut,placeholder="Click, then press shortcut",max_length=48,theme=current.theme));
    label("Height",28,334,190,34); height=slider("{}%".format(value.dropdown.height),270,326,440,54,minimum=10,maximum=100,value=value.dropdown.height,step=1);
    label("Width",28,394,190,34); width=slider("{}%".format(value.dropdown.width),270,386,440,54,minimum=20,maximum=100,value=value.dropdown.width,step=1);
    label("Opacity",28,454,190,34); opacity=slider("{}%".format(int(round(value.dropdown.opacity*100))),270,446,440,54,minimum=20,maximum=100,value=value.dropdown.opacity*100,step=1);
    status=label("Ctrl+F12 is the default global toggle.",28,522,684,46,font_size=16);
    def save(close=False):
        try:
            value.general.font_name=str(font_name.value() or "monospace").strip(); value.general.font_size=int(round(font_size.value)); value.dropdown.shortcut=normalize_shortcut(shortcut.value()); value.dropdown.height=int(round(height.value)); value.dropdown.width=int(round(width.value)); value.dropdown.opacity=float(opacity.value)/100.0; path=save_preferences(value); result=install_dropdown_shortcut(value,apply=True);
            send_command("reload"); status.text="Saved {} — {}".format(path,result.detail);
            if close: app().running=False;
        except Exception as exc:
            status.text="Could not apply preferences: {}".format(exc);
    button("APPLY",310,600,180,54,do=lambda:save(False)); button("SAVE && CLOSE",510,600,200,54,do=lambda:save(True));
    start(); return 0;

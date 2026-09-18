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
import shlex;
import warnings;

from sumkeyboard.hotkeys import install_global_shortcut, normalize_shortcut;

from .config import load_preferences, save_preferences;
from .ipc import send_command;
from .theme import available_terminal_themes, canonical_theme_name, gui_theme;


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
        from sumgui.fontpicker import FontPicker;
        from sumgui.widgets import TextInput;
    except ImportError as exc: raise RuntimeError("sumTerminal preferences require sumGUI/Pygame") from exc;
    value.general.theme=canonical_theme_name(value.general.theme); themes=list(available_terminal_themes());
    current=window("SUM Terminal Preferences",width=760,height=950,base_width=760,base_height=950,theme=gui_theme(value.general.theme),font_name=value.general.font_name,font_size=18);
    class ShortcutInput(TextInput):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs); self.capturing=False; self._before=self.value();
        def handle_event(self,event):
            if event.type==pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                self.capturing=True; self._before=self.value(); self.set_value(""); self.placeholder="Press shortcut..."; self.has_focus=True; return True;
            if self.capturing and event.type==pygame.MOUSEBUTTONDOWN and not self.rect.collidepoint(event.pos):
                self.set_value(self._before); self.capturing=False; return False;
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
    label("General",28,72,650,34,font_size=20,bold=True);
    label("Default shell",28,116,200,34); shell=current.add(TextInput(current.rect(270,110,440,42),current.font,text=value.general.shell,placeholder="sumbash / bash -l / zsh / pwsh ...",max_length=160,theme=current.theme));
    label("Appearance",28,172,650,34,font_size=20,bold=True);
    label("Theme",28,216,200,34); theme_name=current.add(TextInput(current.rect(270,210,318,42),current.font,text=value.general.theme,placeholder="Dark / ZX / DOS / user theme",max_length=96,theme=current.theme));
    def cycle_theme(step):
        names=list(available_terminal_themes());
        if not names: return;
        wanted=str(theme_name.value() or value.general.theme).casefold(); index=next((pos for pos,item in enumerate(names) if str(item).casefold()==wanted),0); theme_name.set_value(names[(index+int(step))%len(names)]);
    button("<",598,210,50,42,do=lambda:cycle_theme(-1)); button(">",658,210,50,42,do=lambda:cycle_theme(1));
    label("Font",28,270,200,34);
    font_picker=current.add(FontPicker(current.rect(270,264,440,220),current.font,family=value.general.font_name,bold=value.general.font_bold,italic=value.general.font_italic,small_caps=value.general.font_small_caps,small_caps_scale=value.general.font_small_caps_scale,theme=current.theme,monospace_only=True,max_rows=9,show_scale=True,preview=True,preview_size=22));
    label("Font size",28,494,200,34); font_size=slider("{} pt".format(value.general.font_size),270,486,440,50,minimum=8,maximum=48,value=value.general.font_size,step=1);
    label("Drop-down",28,546,650,34,font_size=20,bold=True);
    label("Shortcut",28,584,230,34); shortcut=current.add(ShortcutInput(current.rect(270,578,440,42),current.font,text=value.dropdown.shortcut,placeholder="Click, then press shortcut",max_length=48,theme=current.theme));
    label("Height",28,636,190,34); height=slider("{}%".format(value.dropdown.height),270,628,440,50,minimum=10,maximum=100,value=value.dropdown.height,step=1);
    label("Width",28,688,190,34); width=slider("{}%".format(value.dropdown.width),270,680,440,50,minimum=20,maximum=100,value=value.dropdown.width,step=1);
    label("Opacity",28,740,190,34); opacity=slider("{}%".format(int(round(value.dropdown.opacity*100))),270,732,440,50,minimum=20,maximum=100,value=value.dropdown.opacity*100,step=1);
    status=label("Fonts filter as you type. Ctrl++ / Ctrl+- zoom; Ctrl+0 resets to the saved size.",28,790,684,48,font_size=15);
    def save(close=False):
        try:
            shell_value=str(shell.value() or "sumbash").strip();
            if not shell_value: shell_value="sumbash";
            if shell_value.casefold()!="sumbash" and not shlex.split(shell_value): raise ValueError("default shell command is empty");
            font_selection=font_picker.selection(); value.general.shell=shell_value; value.general.theme=canonical_theme_name(theme_name.value(),strict=True); value.general.font_name=str(font_selection.family or "monospace").strip(); value.general.font_bold=bool(font_selection.bold); value.general.font_italic=bool(font_selection.italic); value.general.font_small_caps=bool(font_selection.small_caps); value.general.font_small_caps_scale=float(font_selection.small_caps_scale); value.general.font_size=int(round(font_size.value)); value.dropdown.shortcut=normalize_shortcut(shortcut.value() or getattr(shortcut,"_before","") or value.dropdown.shortcut); value.dropdown.height=int(round(height.value)); value.dropdown.width=int(round(width.value)); value.dropdown.opacity=float(opacity.value)/100.0; path=save_preferences(value); result=install_dropdown_shortcut(value,apply=True);
            send_command("reload"); status.text="Saved {} — {}. Active terminal applies after Preferences closes.".format(path,result.detail);
            if close: app().running=False;
        except Exception as exc:
            status.text="Could not apply preferences: {}".format(exc);
    button("APPLY",310,870,180,54,do=lambda:save(False)); button("SAVE && CLOSE",510,870,200,54,do=lambda:save(True));
    start(); return 0;

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


def _monospace_fonts(pygame,current=""):
    names=[]; seen=set();
    for name in [str(current or "").strip(),"monospace",*list(pygame.font.get_fonts())]:
        if not name or name.casefold() in seen: continue;
        try:
            font=pygame.font.SysFont(name,16); widths=[font.size(char)[0] for char in "iMW0@#_"];
        except Exception: continue;
        if max(widths)-min(widths)>1: continue;
        seen.add(name.casefold()); names.append(name);
    return tuple(names);




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
        from sumgui.widgets import TextInput, draw_clipped_text;
    except ImportError as exc: raise RuntimeError("sumTerminal preferences require sumGUI/Pygame") from exc;
    value.general.theme=canonical_theme_name(value.general.theme); themes=list(available_terminal_themes());
    current=window("SUM Terminal Preferences",width=760,height=850,base_width=760,base_height=850,theme=gui_theme(value.general.theme),font_name=value.general.font_name,font_size=18);
    class FontCombo(TextInput):
        def __init__(self,*args,items=(),**kwargs):
            super().__init__(*args,**kwargs); self.items=tuple(items); self.open=False; self.offset=0; self.max_rows=8;
        def popup_rect(self):
            rows=min(self.max_rows,len(self.items)); return pygame.Rect(self.rect.x,self.rect.bottom+2,self.rect.width,max(0,rows*30));
        def get_rect(self):
            return self.rect.union(self.popup_rect()) if self.open else self.rect;
        def _visible_items(self):
            return self.items[self.offset:self.offset+self.max_rows];
        def _select(self,index):
            if 0<=index<len(self.items): self.set_value(self.items[index]); self.open=False; return True;
            return False;
        def _current_index(self):
            probe=self.value().casefold(); return next((i for i,item in enumerate(self.items) if item.casefold()==probe),0);
        def handle_event(self,event):
            if event.type==pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos): self.open=not self.open; self.has_focus=True; return True;
                if self.open and self.popup_rect().collidepoint(event.pos):
                    row=max(0,(event.pos[1]-self.popup_rect().y)//30); return self._select(self.offset+row);
                if self.open: self.open=False; return False;
            if event.type==pygame.MOUSEWHEEL and self.open:
                limit=max(0,len(self.items)-self.max_rows); self.offset=max(0,min(limit,self.offset-int(event.y))); return True;
            if event.type==pygame.KEYDOWN and self.has_focus:
                if event.key in (pygame.K_F4,pygame.K_RETURN): self.open=not self.open; return True;
                if event.key==pygame.K_ESCAPE and self.open: self.open=False; return True;
                if event.key in (pygame.K_UP,pygame.K_DOWN):
                    index=self._current_index()+(-1 if event.key==pygame.K_UP else 1); index=max(0,min(len(self.items)-1,index));
                    if self.items: self.set_value(self.items[index]); self.offset=max(0,min(index,max(0,len(self.items)-self.max_rows)));
                    return True;
            return super().handle_event(event);
        def draw(self,screen):
            super().draw(screen); arrow=pygame.Rect(self.rect.right-34,self.rect.y,34,self.rect.height); pygame.draw.rect(screen,self.theme.button,arrow,border_radius=6); pygame.draw.rect(screen,self.theme.line,arrow,1,border_radius=6); draw_clipped_text(screen,self.font,"▼",self.theme.button_text,arrow,align="center",valign="middle");
            if not self.open: return;
            popup=self.popup_rect(); pygame.draw.rect(screen,self.theme.panel,popup); pygame.draw.rect(screen,self.theme.line,popup,2);
            for row,item in enumerate(self._visible_items()):
                rect=pygame.Rect(popup.x+2,popup.y+row*30,popup.width-4,30);
                if item.casefold()==self.value().casefold(): pygame.draw.rect(screen,self.theme.button_alt,rect);
                draw_clipped_text(screen,self.font,item,self.theme.text,rect.inflate(-8,-2),valign="middle");
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
    label("General",28,72,650,34,font_size=20,bold=True);
    label("Default shell",28,116,200,34); shell=current.add(TextInput(current.rect(270,110,440,42),current.font,text=value.general.shell,placeholder="sumbash / bash -l / zsh / pwsh ...",max_length=160,theme=current.theme));
    label("Appearance",28,172,650,34,font_size=20,bold=True);
    label("Theme",28,216,200,34); theme_name=current.add(TextInput(current.rect(270,210,318,42),current.font,text=value.general.theme,placeholder="Dark / ZX / DOS / user theme",max_length=96,theme=current.theme));
    def cycle_theme(step):
        names=list(available_terminal_themes());
        if not names: return;
        wanted=str(theme_name.value() or value.general.theme).casefold(); index=next((pos for pos,item in enumerate(names) if str(item).casefold()==wanted),0); theme_name.set_value(names[(index+int(step))%len(names)]);
    button("<",598,210,50,42,do=lambda:cycle_theme(-1)); button(">",658,210,50,42,do=lambda:cycle_theme(1));
    label("Font",28,270,200,34); font_name=None;
    label("Font size",28,324,200,34); font_size=slider("{} pt".format(value.general.font_size),270,316,440,54,minimum=8,maximum=48,value=value.general.font_size,step=1);
    label("Drop-down",28,386,650,34,font_size=20,bold=True);
    label("Shortcut",28,432,230,34); shortcut=current.add(ShortcutInput(current.rect(270,426,440,42),current.font,text=value.dropdown.shortcut,placeholder="Click, then press shortcut",max_length=48,theme=current.theme));
    label("Height",28,488,190,34); height=slider("{}%".format(value.dropdown.height),270,480,440,54,minimum=10,maximum=100,value=value.dropdown.height,step=1);
    label("Width",28,548,190,34); width=slider("{}%".format(value.dropdown.width),270,540,440,54,minimum=20,maximum=100,value=value.dropdown.width,step=1);
    label("Opacity",28,608,190,34); opacity=slider("{}%".format(int(round(value.dropdown.opacity*100))),270,600,440,54,minimum=20,maximum=100,value=value.dropdown.opacity*100,step=1);
    font_name=current.add(FontCombo(current.rect(270,264,440,42),current.font,text=value.general.font_name,placeholder="monospace font",max_length=96,theme=current.theme,items=_monospace_fonts(pygame,value.general.font_name)));
    status=label("Theme changes hot-reload the terminal. Ctrl+F12 toggles; Ctrl+Shift+T opens a tab.",28,674,684,48,font_size=15);
    def save(close=False):
        try:
            shell_value=str(shell.value() or "sumbash").strip();
            if not shell_value: shell_value="sumbash";
            if shell_value.casefold()!="sumbash" and not shlex.split(shell_value): raise ValueError("default shell command is empty");
            value.general.shell=shell_value; value.general.theme=canonical_theme_name(theme_name.value(),strict=True); value.general.font_name=str(font_name.value() or "monospace").strip(); value.general.font_size=int(round(font_size.value)); value.dropdown.shortcut=normalize_shortcut(shortcut.value()); value.dropdown.height=int(round(height.value)); value.dropdown.width=int(round(width.value)); value.dropdown.opacity=float(opacity.value)/100.0; path=save_preferences(value); result=install_dropdown_shortcut(value,apply=True);
            send_command("reload"); status.text="Saved {} — {}. Active terminal applies after Preferences closes.".format(path,result.detail);
            if close: app().running=False;
        except Exception as exc:
            status.text="Could not apply preferences: {}".format(exc);
    button("APPLY",310,770,180,54,do=lambda:save(False)); button("SAVE && CLOSE",510,770,200,54,do=lambda:save(True));
    start(); return 0;

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
        from sumgui.easy import app, start, window;
        from sumgui.fontpicker import FontPicker;
        from sumgui.widgets import Button, CheckBox, Label, ScrollPanel, Slider, TextInput;
    except ImportError as exc: raise RuntimeError("sumTerminal preferences require sumGUI/Pygame") from exc;
    value.general.theme=canonical_theme_name(value.general.theme); themes=list(available_terminal_themes());
    current=window("SUM Terminal Preferences",width=760,height=820,base_width=760,base_height=820,theme=gui_theme(value.general.theme),font_name=value.general.font_name,font_size=18);

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

    def root_rect(x,y,w,h): return current.rect(x,y,w,h);
    def local_rect(x,y,w,h): return pygame.Rect(current.w(x),current.h(y),current.w(w),current.h(h));
    def font(size=18,bold=False): return current.make_font(size,bold=bold);
    def body_label(text,x,y,w=220,h=34,size=18,bold=False): return body.add(Label(local_rect(x,y,w,h),text,font(size,bold),current.theme));
    def body_button(text,x,y,w,h,callback):
        def clicked(_widget): callback();
        return body.add(Button(local_rect(x,y,w,h),text,font(18,True),clicked,current.theme));

    current.add(Label(root_rect(28,16,680,42),"SUM Terminal Preferences",font(26,True),current.theme));
    body=current.add(ScrollPanel(root_rect(20,68,720,640),content_height=current.h(1000),theme=current.theme,scrollbar_width=current.w(16),wheel_step=current.h(52)));

    body_label("General",8,8,650,34,20,True);
    body_label("Default shell",8,50,220,34); shell=body.add(TextInput(local_rect(242,44,430,42),current.font,text=value.general.shell,placeholder="sumbash / bash -l / zsh / pwsh ...",max_length=160,theme=current.theme));

    body_label("Appearance",8,104,650,34,20,True);
    body_label("Theme",8,146,220,34); theme_name=body.add(TextInput(local_rect(242,140,308,42),current.font,text=value.general.theme,placeholder="Dark / ZX / DOS / user theme",max_length=96,theme=current.theme));
    def cycle_theme(step):
        names=list(available_terminal_themes());
        if not names: return;
        wanted=str(theme_name.value() or value.general.theme).casefold(); index=next((pos for pos,item in enumerate(names) if str(item).casefold()==wanted),0); theme_name.set_value(names[(index+int(step))%len(names)]);
    body_button("<",560,140,50,42,lambda:cycle_theme(-1)); body_button(">",620,140,50,42,lambda:cycle_theme(1));

    body_label("Font",8,200,220,34);
    font_picker=body.add(FontPicker(local_rect(242,194,430,220),current.font,family=value.general.font_name,bold=value.general.font_bold,italic=value.general.font_italic,small_caps=value.general.font_small_caps,small_caps_scale=value.general.font_small_caps_scale,uppercase_embolden=value.general.font_uppercase_embolden,lowercase_embolden=value.general.font_lowercase_embolden,theme=current.theme,monospace_only=True,max_rows=9,show_scale=True,show_weights=True,preview=True,preview_size=22));
    # Local rectangles are already expressed in scaled content coordinates.
    font_size_top=font_picker.rect.bottom+current.h(10);
    body.add(Label(pygame.Rect(current.w(8),font_size_top,current.w(220),current.h(34)),"Font size",font(18),current.theme));
    font_size=body.add(Slider(pygame.Rect(current.w(242),font_size_top-current.h(8),current.w(430),current.h(50)),minimum=8,maximum=48,value=value.general.font_size,step=1,font=current.font,label="{} pt".format(value.general.font_size),theme=current.theme));
    tray_top=font_size_top+current.h(58);
    show_tray=body.add(CheckBox(pygame.Rect(current.w(242),tray_top,current.w(430),current.h(38)),"Show systray icon (Σtl)",current.font,checked=value.general.show_tray,theme=current.theme));

    dropdown_top=tray_top+current.h(60);
    body.add(Label(pygame.Rect(current.w(8),dropdown_top,current.w(650),current.h(34)),"Drop-down",font(20,True),current.theme));
    y=dropdown_top+current.h(42);
    body.add(Label(pygame.Rect(current.w(8),y,current.w(220),current.h(34)),"Shortcut",font(18),current.theme)); shortcut=body.add(ShortcutInput(pygame.Rect(current.w(242),y-current.h(6),current.w(430),current.h(42)),current.font,text=value.dropdown.shortcut,placeholder="Click, then press shortcut",max_length=48,theme=current.theme));
    y+=current.h(54);
    body.add(Label(pygame.Rect(current.w(8),y,current.w(190),current.h(34)),"Height",font(18),current.theme)); height=body.add(Slider(pygame.Rect(current.w(242),y-current.h(8),current.w(430),current.h(50)),minimum=10,maximum=100,value=value.dropdown.height,step=1,font=current.font,label="{}%".format(value.dropdown.height),theme=current.theme));
    y+=current.h(54);
    body.add(Label(pygame.Rect(current.w(8),y,current.w(190),current.h(34)),"Width",font(18),current.theme)); width=body.add(Slider(pygame.Rect(current.w(242),y-current.h(8),current.w(430),current.h(50)),minimum=20,maximum=100,value=value.dropdown.width,step=1,font=current.font,label="{}%".format(value.dropdown.width),theme=current.theme));
    y+=current.h(54);
    body.add(Label(pygame.Rect(current.w(8),y,current.w(190),current.h(34)),"Opacity",font(18),current.theme)); opacity=body.add(Slider(pygame.Rect(current.w(242),y-current.h(8),current.w(430),current.h(50)),minimum=20,maximum=100,value=value.dropdown.opacity*100,step=1,font=current.font,label="{}%".format(int(round(value.dropdown.opacity*100))),theme=current.theme));
    body.set_content_height(y+current.h(72));

    status=current.add(Label(root_rect(28,716,684,34),"Font preview is live. Mouse wheel scrolls this panel.",font(14),current.theme));

    def save(close=False):
        try:
            shell_value=str(shell.value() or "sumbash").strip();
            if not shell_value: shell_value="sumbash";
            if shell_value.casefold()!="sumbash" and not shlex.split(shell_value): raise ValueError("default shell command is empty");
            font_selection=font_picker.selection(); value.general.shell=shell_value; value.general.theme=canonical_theme_name(theme_name.value(),strict=True); value.general.font_name=str(font_selection.family or "monospace").strip(); value.general.font_bold=bool(font_selection.bold); value.general.font_italic=bool(font_selection.italic); value.general.font_small_caps=bool(font_selection.small_caps); value.general.font_small_caps_scale=float(font_selection.small_caps_scale); value.general.font_uppercase_embolden=int(font_selection.uppercase_embolden); value.general.font_lowercase_embolden=int(font_selection.lowercase_embolden); value.general.font_size=int(round(font_size.value)); value.general.show_tray=bool(show_tray.checked); value.dropdown.shortcut=normalize_shortcut(shortcut.value() or getattr(shortcut,"_before","") or value.dropdown.shortcut); value.dropdown.height=int(round(height.value)); value.dropdown.width=int(round(width.value)); value.dropdown.opacity=float(opacity.value)/100.0; path=save_preferences(value); result=install_dropdown_shortcut(value,apply=True);
            send_command("reload"); status.text="Saved {} — {}. Active terminal applies after Preferences closes.".format(path,result.detail);
            if close: app().running=False;
        except Exception as exc:
            status.text="Could not apply preferences: {}".format(exc);

    def root_button(text,x,y,w,h,callback):
        def clicked(_widget): callback();
        return current.add(Button(root_rect(x,y,w,h),text,font(18,True),clicked,current.theme));
    root_button("APPLY",310,754,180,50,lambda:save(False)); root_button("SAVE && CLOSE",510,754,200,50,lambda:save(True));
    start(); return 0;


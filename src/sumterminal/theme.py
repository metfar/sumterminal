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
from sumtui.theme import THEMES, available_theme_names, refresh_user_themes;


_XTERM_ANSI16=(
    (0,0,0),(205,0,0),(0,205,0),(205,205,0),(0,0,238),(205,0,205),(0,205,205),(229,229,229),
    (127,127,127),(255,0,0),(0,255,0),(255,255,0),(92,92,255),(255,0,255),(0,255,255),(255,255,255),
);
_BUILTIN_PALETTE_MAP={
    "ZX":(0,2,4,6,1,3,5,7,8,10,12,14,9,11,13,15),
    "DOS":(0,4,2,6,1,5,3,7,8,12,10,14,9,13,11,15),
    "XBASE":(0,4,2,6,1,5,3,7,8,12,10,14,9,13,11,15),
    "C64":(0,2,5,7,6,4,3,1,11,10,13,7,14,4,3,1),
};


def available_terminal_themes():
    refresh_user_themes();
    return available_theme_names();


def resolve_theme(name="Dark"):
    refresh_user_themes();
    wanted=str(name or "Dark").strip().casefold();
    for actual,theme in THEMES.items():
        if str(actual).casefold()==wanted: return theme;
    return THEMES.get("Dark") or next(iter(THEMES.values()));


def canonical_theme_name(name="Dark",strict=False):
    refresh_user_themes(); wanted=str(name or "Dark").strip().casefold();
    for actual,theme in THEMES.items():
        if str(actual).casefold()==wanted: return str(theme.name);
    if strict: raise ValueError("unknown SUM theme: {}".format(name));
    return str((THEMES.get("Dark") or next(iter(THEMES.values()))).name);


def terminal_ansi16(theme):
    value=resolve_theme(theme) if isinstance(theme,str) else theme;
    palette=list(tuple(getattr(value,"palette",()) or ()));
    if str(getattr(value,"name","")).casefold() in ("dark","light"): return tuple(_XTERM_ANSI16);
    mapping=_BUILTIN_PALETTE_MAP.get(str(getattr(value,"name","")));
    if mapping is not None and len(palette)>=16: return tuple(tuple(palette[index]) for index in mapping);
    normalized=[tuple(color) for color in palette[:16]];
    if len(normalized)<16: normalized.extend(_XTERM_ANSI16[len(normalized):]);
    return tuple(normalized[:16]);


def terminal_colors(theme):
    value=resolve_theme(theme) if isinstance(theme,str) else theme;
    foreground=tuple(getattr(value,"viewer_text",None) or getattr(value,"text",(229,229,229)));
    background=tuple(getattr(value,"viewer_bg",None) or getattr(value,"bg",(0,0,0)));
    cursor=tuple(getattr(value,"cursor",(255,255,0)));
    selection_bg=tuple(getattr(value,"selection_bg",(60,100,120)));
    selection_text=tuple(getattr(value,"selection_text",(255,255,255)));
    return foreground,background,cursor,selection_bg,selection_text;


def gui_theme(theme):
    value=resolve_theme(theme) if isinstance(theme,str) else theme;
    from sumgui.theme import Theme as GuiTheme;
    return GuiTheme(
        name=value.name,
        bg=tuple(value.bg),
        panel=tuple(value.panel),
        line=tuple(value.line),
        text=tuple(value.text),
        muted=tuple(value.muted),
        button=tuple(value.button),
        button_alt=tuple(value.button_alt),
        button_text=tuple(value.button_text),
        error=tuple(value.error),
        cursor=tuple(value.cursor),
        palette=list(tuple(value.palette or ())),
        selection_bg=tuple(value.selection_bg),
        selection_text=tuple(value.selection_text),
        title=tuple(value.title),
        viewer_bg=tuple(value.viewer_bg),
        viewer_text=tuple(value.viewer_text),
    );

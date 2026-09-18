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
import os;
import select;
import sys;
import time;

import pytest;

from sumterminal import SessionState, TerminalDecoder, TerminalSession, TerminalSize;
from sumterminal.session import default_shell_command;


def _collect(session,timeout=3.0):
    deadline=time.monotonic()+timeout; data=bytearray(); eof=False;
    while time.monotonic()<deadline:
        ready,_,_=select.select([session.fileno],[],[],0.05);
        if ready:
            result=session.read_result(65536);
            data.extend(result.data or b"");
            if result.eof: eof=True;
        if session.poll() is not None and eof: break;
    return bytes(data);


def test_incremental_utf8_decoder_keeps_split_codepoint():
    decoder=TerminalDecoder(); value="π".encode("utf-8");
    assert decoder.feed(value[:1])=="";
    assert decoder.feed(value[1:])=="π";


def test_terminal_size_normalizes_positive_values():
    assert TerminalSize(0,-4).normalized()==TerminalSize(1,1);


def test_default_shell_prefers_configured_value():
    assert default_shell_command({"SUM_TERMINAL_SHELL":"python -q"})==["python","-q"];


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_posix_session_captures_output_and_exit(tmp_path):
    session=TerminalSession(command=[sys.executable,"-c","print('HELLO-PTY')"],cwd=str(tmp_path)).start();
    try:
        output=_collect(session);
        assert b"HELLO-PTY" in output;
        assert session.wait(timeout=2.0)==0;
        assert session.state is SessionState.EXITED;
    finally: session.close();


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_posix_session_write_and_read(tmp_path):
    code="import sys; print('READY',flush=True); value=sys.stdin.readline().strip(); print('GOT:'+value,flush=True)";
    session=TerminalSession(command=[sys.executable,"-u","-c",code],cwd=str(tmp_path)).start();
    try:
        time.sleep(0.05); session.write(b"alpha\n"); output=_collect(session);
        assert b"READY" in output;
        assert b"GOT:alpha" in output;
        assert session.wait(timeout=2.0)==0;
    finally: session.close();


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_posix_resize_reaches_child(tmp_path):
    session=TerminalSession(command=["/bin/sh"],cwd=str(tmp_path),rows=24,columns=80).start();
    try:
        session.resize(37,101);
        session.write(b"stty size; exit\n");
        output=_collect(session);
        assert b"37 101" in output.replace(b"\r",b"");
        assert session.wait(timeout=2.0)==0;
    finally: session.close();



@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_default_session_starts_sumbash(tmp_path):
    session=TerminalSession(cwd=str(tmp_path)).start();
    try:
        session.write(b"echo DEFAULT-SUMBASH\nexit\n");
        output=_collect(session,timeout=4.0);
        assert b"DEFAULT-SUMBASH" in output;
        assert session.wait(timeout=2.0)==0;
    finally: session.close();


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_read_event_exposes_raw_and_decoded_text(tmp_path):
    session=TerminalSession(command=[sys.executable,"-c","print('pi=\u03c0')"],cwd=str(tmp_path)).start();
    try:
        deadline=time.monotonic()+3.0; events=[];
        while time.monotonic()<deadline:
            ready,_,_=select.select([session.fileno],[],[],0.05);
            if ready:
                event=session.read_event();
                if event is not None: events.append(event);
            if session.poll() is not None and any(event.kind=="eof" for event in events): break;
        raw=b"".join(event.raw for event in events if event.kind=="output");
        text="".join(event.text for event in events if event.kind=="output");
        assert "pi=π" in text;
        assert "pi=π".encode("utf-8") in raw;
    finally:
        try: session.wait(timeout=2.0);
        except Exception: pass;
        session.close();

def test_cli_version(capsys):
    from sumterminal.cli import main;
    with pytest.raises(SystemExit) as exc:
        main(["--version"]);
    assert exc.value.code==0;
    assert "sumterminal 0.1.0a19" in capsys.readouterr().out;


def test_terminal_session_advertises_its_own_capabilities(tmp_path):
    session=TerminalSession(command=[sys.executable,"-c","pass"],cwd=str(tmp_path),env={});
    assert session.env["TERM"]=="xterm-256color";
    assert session.env["COLORTERM"]=="truecolor";
    assert session.env["TERM_PROGRAM"]=="sumterminal";
    assert session.env["SUM_TERMINAL"]=="1";


def test_terminal_session_preserves_explicit_term(tmp_path):
    session=TerminalSession(command=[sys.executable,"-c","pass"],cwd=str(tmp_path),env={"TERM":"vt100"});
    assert session.env["TERM"]=="vt100";


def test_preferences_default_to_gui_and_ctrl_f12(tmp_path):
    from sumterminal.config import TerminalPreferences, load_preferences, save_preferences;
    path=tmp_path/"terminal.toml"; value=TerminalPreferences(); save_preferences(value,path); loaded=load_preferences(path);
    assert loaded.general.frontend=="gui";
    assert loaded.dropdown.shortcut=="Ctrl+F12";
    assert loaded.dropdown.height==45;
    assert loaded.dropdown.width==100;
    assert loaded.dropdown.opacity==pytest.approx(0.94);
    assert loaded.general.font_name=="monospace";
    assert loaded.general.font_size==18;
    assert loaded.general.font_bold is False;
    assert loaded.general.font_italic is False;
    assert loaded.general.font_small_caps is False;
    assert loaded.general.shell=="sumbash";


def test_terminal_screen_cursor_sgr_and_title():
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(4,12); screen.feed("abc\x1b[31mR\x1b[0m\r\nnext\x1b]0;demo\x07");
    assert screen.text_lines()[0].startswith("abcR");
    assert screen.lines[0][3].fg==(205,0,0);
    assert screen.text_lines()[1].startswith("next");
    assert screen.title=="demo";


def test_terminal_screen_alternate_buffer_restores_primary():
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(3,8); screen.feed("main"); screen.feed("\x1b[?1049h"); screen.feed("alt");
    assert screen.text_lines()[0].startswith("alt");
    screen.feed("\x1b[?1049l");
    assert screen.text_lines()[0].startswith("main");


def test_cli_gui_reports_missing_frontend(monkeypatch,capsys):
    from sumterminal import cli;
    monkeypatch.setattr(cli.GuiTerminalView,"available",staticmethod(lambda:False));
    code=cli.main(["--gui","--",sys.executable,"-c","print('x')"]);
    assert code==1;
    assert "graphical frontend requested" in capsys.readouterr().err;


def test_dropdown_geometry_uses_preferences():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    class Display:
        @staticmethod
        def get_desktop_sizes(): return [(2000,1000)];
    fake_pygame=SimpleNamespace(display=Display());
    session=SimpleNamespace(size=TerminalSize(24,80)); prefs=TerminalPreferences(); prefs.dropdown.width=80; prefs.dropdown.height=40;
    view=GuiTerminalView(session,preferences=prefs,drop_down=True);
    assert view._geometry(fake_pygame)==(1600,400,200,0);


def test_dropdown_ipc_toggle_roundtrip(tmp_path):
    import time;
    from sumterminal.ipc import DropdownIPCServer, send_command;
    path=tmp_path/"terminal.sock"; server=DropdownIPCServer(path); assert server.start() is True;
    try:
        assert send_command("toggle",path=path,timeout=1.0) is True;
        deadline=time.monotonic()+1.0; values=[];
        while time.monotonic()<deadline and not values:
            values=server.pending(); time.sleep(0.01);
        assert values==["toggle"];
    finally: server.close();


def test_terminal_screen_ansi_16_256_and_truecolor():
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(2,16);
    screen.feed('\x1b[1;34mB\x1b[38;5;196mR\x1b[38;2;12;34;56mT\x1b[0m');
    assert screen.lines[0][0].fg==(0,0,238);
    assert screen.lines[0][0].bold is True;
    assert screen.lines[0][1].fg==(255,0,0);
    assert screen.lines[0][2].fg==(12,34,56);


def test_bold_ansi_base_color_maps_to_bright_display_color():
    from sumterminal.gui import _display_fg;
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen();
    assert _display_fg(screen,(0,0,238),True)==(92,92,255);
    assert _display_fg(screen,(12,34,56),True)==(12,34,56);


def test_gui_font_metrics_fall_back_to_monospace_for_proportional_font():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    class FakeFont:
        def __init__(self,name,size): self.name=name; self._size=size;
        def size(self,text):
            if self.name=="proportional": return ((3 if text=="i" else 9)*len(text),16);
            return (7*len(text),16);
        def get_linesize(self): return 20;
        def get_height(self): return 16;
    class FontAPI:
        @staticmethod
        def match_font(name,bold=False): return None;
        @staticmethod
        def Font(path,size): return FakeFont("file",size);
        @staticmethod
        def SysFont(name,size,bold=False): return FakeFont(name,size);
    fake=SimpleNamespace(font=FontAPI());
    prefs=TerminalPreferences(); prefs.general.font_name="proportional"; prefs.general.font_size=18;
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs);
    view._make_fonts(fake);
    assert view.effective_font_name=="monospace";
    assert view.cell_width==7;
    assert view.cell_height==20;
    assert view.glyph_height==16;
    assert view.glyph_offset_y==2;


def test_preferences_persist_default_shell(tmp_path):
    from sumterminal.config import TerminalPreferences, load_preferences, save_preferences;
    path=tmp_path/"terminal.toml"; value=TerminalPreferences(); value.general.shell="bash -l"; save_preferences(value,path); loaded=load_preferences(path);
    assert loaded.general.shell=="bash -l";


def test_cli_print_default_shell_uses_preferences(monkeypatch,capsys):
    from sumterminal import cli;
    from sumterminal.config import TerminalPreferences;
    value=TerminalPreferences(); value.general.shell="python -q";
    monkeypatch.setattr(cli,"load_preferences",lambda:value);
    assert cli.main(["--print-default-shell"])==0;
    assert capsys.readouterr().out.strip()=="python -q";


def test_gui_preferred_shell_command_uses_preference():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    prefs=TerminalPreferences(); prefs.general.shell="bash -l";
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs);
    assert view._preferred_shell_command()==["bash","-l"];
    prefs.general.shell="sumbash";
    assert view._preferred_shell_command() is None;


def test_ctrl_shift_t_creates_new_tab(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    fake_pygame=SimpleNamespace(KMOD_CTRL=1,KMOD_SHIFT=2,K_F12=10,K_COMMA=11,K_t=12);
    event=SimpleNamespace(key=12,mod=3); session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=TerminalPreferences()); called=[];
    monkeypatch.setattr(view,"_new_tab",lambda:called.append(True));
    assert view._key_bytes(fake_pygame,event)==b"";
    assert called==[True];


def test_tab_label_uses_shell_name():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(24,80),argv=("/usr/bin/sumbash",)); view=GuiTerminalView(session,preferences=TerminalPreferences());
    assert view._tab_label(view.active_tab,0)=="sumbash";


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_new_tab_starts_configured_default_shell(tmp_path):
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    initial=TerminalSession(command=["/bin/sh"],cwd=str(tmp_path)).start(); prefs=TerminalPreferences(); prefs.general.shell="/bin/sh"; view=GuiTerminalView(initial,preferences=prefs);
    try:
        tab=view._new_tab();
        assert tab is not None;
        assert view.tab_count==2;
        assert tuple(view.session.argv)==("/bin/sh",);
        view.session.write(b"echo TAB-OK; exit\n");
        output=_collect(view.session);
        assert b"TAB-OK" in output;
    finally:
        for item in list(view._tabs):
            if item.session.poll() is None: item.session.terminate();
            try: item.session.wait(timeout=1.0);
            except Exception: pass;
            item.session.close();


def test_terminal_theme_resolves_sum_builtin_and_ansi_palette():
    from sumterminal.theme import resolve_theme, terminal_ansi16, terminal_colors;
    theme=resolve_theme("DOS"); palette=terminal_ansi16(theme); foreground,background,cursor,_selection_bg,_selection_text=terminal_colors(theme);
    assert theme.name=="DOS";
    assert palette[1]==(170,0,0);
    assert palette[4]==(0,0,170);
    assert foreground==theme.viewer_text;
    assert background==theme.viewer_bg;
    assert cursor==theme.cursor;


def test_terminal_screen_palette_hot_reload_recolors_indexed_cells():
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(2,12); screen.feed("\x1b[31mR\x1b[0mX"); palette=list(screen.ansi16); palette[1]=(1,2,3); new_fg=(210,220,230); new_bg=(4,5,6);
    screen.set_palette(tuple(palette),default_fg=new_fg,default_bg=new_bg,remap=True);
    assert screen.lines[0][0].fg==(1,2,3);
    assert screen.lines[0][1].fg==new_fg;
    assert screen.lines[0][1].bg==new_bg;
    screen.feed("\x1b[38;5;1mY");
    assert screen.lines[0][2].fg==(1,2,3);


def test_preferences_persist_theme(tmp_path):
    from sumterminal.config import TerminalPreferences, load_preferences, save_preferences;
    path=tmp_path/"terminal.toml"; value=TerminalPreferences(); value.general.theme="DOS"; save_preferences(value,path); loaded=load_preferences(path);
    assert loaded.general.theme=="DOS";


def test_cli_lists_available_themes(capsys):
    from sumterminal.cli import main;
    assert main(["--list-themes"])==0;
    output=capsys.readouterr().out.splitlines();
    assert "Dark" in output;
    assert "DOS" in output;


def test_cli_theme_option_is_parsed():
    from sumterminal.cli import parser;
    args=parser().parse_args(["--theme","Light","--host"]);
    assert args.theme=="Light";
    assert args.host is True;


def test_user_sum_theme_is_available_to_terminal(tmp_path,monkeypatch):
    import json;
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path));
    from sumtui.theme import make_theme, theme_to_dict;
    from sumterminal.theme import available_terminal_themes, canonical_theme_name, resolve_theme;
    directory=tmp_path/"sumtui"/"themes"; directory.mkdir(parents=True); payload=theme_to_dict(make_theme("Dark").copy(name="Ocean Test",viewer_bg=(1,2,3),viewer_text=(210,220,230))); (directory/"ocean-test.json").write_text(json.dumps(payload),encoding="utf-8");
    assert "Ocean Test" in available_terminal_themes();
    assert canonical_theme_name("ocean test",strict=True)=="Ocean Test";
    assert resolve_theme("Ocean Test").viewer_bg==(1,2,3);


def test_preferences_reload_keeps_existing_display_when_geometry_is_unchanged(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    prefs=TerminalPreferences(); prefs.dropdown.width=100; prefs.dropdown.height=45;
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs,drop_down=True);
    class Surface:
        @staticmethod
        def get_size(): return (2000,450);
    calls=[];
    class Display:
        @staticmethod
        def get_surface(): return Surface();
        @staticmethod
        def get_desktop_sizes(): return [(2000,1000)];
        @staticmethod
        def set_mode(size,flags): calls.append((size,flags)); return Surface();
    fake=SimpleNamespace(display=Display());
    monkeypatch.setattr("sumterminal.gui.load_preferences",lambda:prefs);
    monkeypatch.setattr(view,"_reload_theme",lambda:None);
    monkeypatch.setattr(view,"_make_fonts",lambda pygame:None);
    monkeypatch.setattr(view,"_update_size",lambda *args:None);
    window_calls=[]; monkeypatch.setattr(view,"_apply_window_properties",lambda pygame:window_calls.append(True));
    view._reload_preferences(fake);
    assert calls==[];
    assert window_calls==[];


def test_terminal_session_resize_is_idempotent(tmp_path):
    from types import SimpleNamespace;
    session=TerminalSession(command=[sys.executable,"-c","pass"],cwd=str(tmp_path),rows=24,columns=80);
    calls=[];
    session.adapter=SimpleNamespace(resize=lambda rows,columns:calls.append((rows,columns)) or TerminalSize(rows,columns));
    event=session.resize(24,80);
    assert event.size==TerminalSize(24,80);
    assert calls==[];
    event=session.resize(30,100);
    assert event.size==TerminalSize(30,100);
    assert calls==[(30,100)];


def test_gui_update_size_does_not_repeat_identical_pty_resize():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    class Surface:
        @staticmethod
        def get_size(): return (800,458);
    class Display:
        @staticmethod
        def get_surface(): return Surface();
    fake=SimpleNamespace(display=Display());
    calls=[];
    session=SimpleNamespace(size=TerminalSize(25,100),poll=lambda:None,resize=lambda rows,columns:calls.append((rows,columns)));
    view=GuiTerminalView(session,preferences=TerminalPreferences());
    view.cell_width=8; view.cell_height=16;
    view._update_size(fake,None,58);
    assert view.screen_model.rows==25;
    assert view.screen_model.columns==100;
    assert calls==[];


def test_posix_adapter_resize_ignores_unchanged_size(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.posix import PosixPTYAdapter;
    adapter=PosixPTYAdapter(); adapter.master=SimpleNamespace(fd=123); adapter.size=TerminalSize(24,80); calls=[];
    monkeypatch.setattr(adapter,"_set_winsize_fd",lambda fd,size:calls.append((fd,size)));
    assert adapter.resize(24,80)==TerminalSize(24,80);
    assert calls==[];
    assert adapter.resize(30,90)==TerminalSize(30,90);
    assert calls==[(123,TerminalSize(30,90))];



def test_vt_application_cursor_mode_switches_encoder_sequences():
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(); encoder=TerminalInputEncoder(screen.modes);
    assert encoder.encode_key("up")==b"\x1b[A";
    assert encoder.encode_key("home")==b"\x1b[H";
    screen.feed("\x1b[?1h");
    assert screen.application_cursor_keys is True;
    assert encoder.encode_key("up")==b"\x1bOA";
    assert encoder.encode_key("home")==b"\x1bOH";
    screen.feed("\x1b[?1l");
    assert screen.application_cursor_keys is False;
    assert encoder.encode_key("left")==b"\x1b[D";


def test_terminfo_smkx_and_rmkx_semantics_match_xterm_cursor_and_keypad_modes():
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(); encoder=TerminalInputEncoder(screen.modes);
    screen.feed("\x1b[?1h\x1b=");
    assert screen.application_cursor_keys is True;
    assert screen.application_keypad is True;
    assert encoder.encode_key("up")==b"\x1bOA";
    assert encoder.encode_key("kp1")==b"\x1bOq";
    assert encoder.encode_key("kp_enter")==b"\x1bOM";
    screen.feed("\x1b[?1l\x1b>");
    assert screen.application_cursor_keys is False;
    assert screen.application_keypad is False;
    assert encoder.encode_key("up")==b"\x1b[A";
    assert encoder.encode_key("kp1")==b"1";
    assert encoder.encode_key("kp_enter")==b"\r";


def test_xterm_modified_cursor_and_function_keys_are_encoded_compatibly():
    from sumterminal.input import TerminalInputEncoder;
    encoder=TerminalInputEncoder();
    assert encoder.encode_key("up",shift=True)==b"\x1b[1;2A";
    assert encoder.encode_key("left",alt=True)==b"\x1b[1;3D";
    assert encoder.encode_key("right",ctrl=True)==b"\x1b[1;5C";
    assert encoder.encode_key("down",shift=True,ctrl=True)==b"\x1b[1;6B";
    assert encoder.encode_key("f3",alt=True)==b"\x1b[1;3R";
    assert encoder.encode_key("pageup",shift=True)==b"\x1b[5;2~";
    assert encoder.encode_key("tab",shift=True)==b"\x1b[Z";


def test_alt_printable_and_ctrl_alt_sequences_are_encoded_for_tui_shortcuts():
    from sumterminal.input import TerminalInputEncoder;
    from sumtui.backends.input import AnsiDecoder;
    encoder=TerminalInputEncoder(); decoder=AnsiDecoder(escape_timeout=0.0);
    assert encoder.encode_key("p",alt=True,text="p")==b"\x1bp";
    events=decoder.feed(encoder.encode_key("p",alt=True,text="p")); assert len(events)==1; assert events[0].key=="p"; assert events[0].alt is True;
    assert encoder.encode_key("w",ctrl=True,alt=True)==b"\x1b\x17";
    events=decoder.feed(encoder.encode_key("w",ctrl=True,alt=True)); assert len(events)==1; assert events[0].key=="w"; assert events[0].ctrl is True; assert events[0].alt is True;


def test_sumtui_decoder_accepts_sumterminal_key_sequences():
    from sumterminal.input import TerminalInputEncoder;
    from sumtui.backends.input import AnsiDecoder;
    from sumtui.events import Key;
    encoder=TerminalInputEncoder(); decoder=AnsiDecoder(escape_timeout=0.0);
    cases=((encoder.encode_key("up"),Key.UP,False,False,False),(encoder.encode_key("up",ctrl=True,shift=True),Key.UP,True,False,True),(encoder.encode_key("f3",alt=True),Key.F3,False,True,False),(encoder.encode_key("pageup",shift=True),Key.PAGE_UP,False,False,True));
    for data,key,ctrl,alt,shift in cases:
        events=decoder.feed(data); assert len(events)==1; event=events[0]; assert event.key==key; assert event.ctrl is ctrl; assert event.alt is alt; assert event.shift is shift;


def test_screen_tracks_sumtui_keyboard_reporting_request_without_losing_modes():
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(); encoder=TerminalInputEncoder(screen.modes);
    screen.feed("\x1b[>27u\x1b[=27u");
    assert screen.keyboard_flags==27;
    screen.feed("\x1b[?1h\x1b=");
    assert encoder.encode_key("up")==b"\x1bOA";
    assert encoder.encode_key("kp1")==b"\x1bOq";
    screen.feed("\x1bc");
    assert screen.keyboard_flags==0;
    assert encoder.encode_key("up")==b"\x1b[A";


def test_bracketed_paste_encoder_follows_terminal_mode():
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(); encoder=TerminalInputEncoder(screen.modes);
    assert encoder.encode_paste("alpha\nbeta")==b"alpha\nbeta";
    screen.feed("\x1b[?2004h");
    assert encoder.encode_paste("alpha\nbeta")==b"\x1b[200~alpha\nbeta\x1b[201~";
    screen.feed("\x1b[?2004l");
    assert encoder.encode_paste("x")==b"x";


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_application_cursor_roundtrip_through_real_pty(tmp_path):
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    code="import os,tty; tty.setraw(0); os.write(1,b'\\x1b[?1h\\x1b=READY'); data=os.read(0,3); os.write(1,b'\\r\\nGOT:'+data.hex().encode()+b'\\r\\n')";
    session=TerminalSession(command=[sys.executable,"-u","-c",code],cwd=str(tmp_path)).start(); screen=TerminalScreen(); encoder=TerminalInputEncoder(screen.modes); captured=bytearray();
    try:
        deadline=time.monotonic()+3.0;
        while time.monotonic()<deadline and b"READY" not in captured:
            ready,_,_=select.select([session.fileno],[],[],0.05);
            if ready:
                event=session.read_event(65536);
                if event is not None and event.kind=="output": captured.extend(event.raw); screen.feed(event.text);
        assert b"READY" in captured;
        assert screen.application_cursor_keys is True;
        assert screen.application_keypad is True;
        session.write(encoder.encode_key("up"));
        captured.extend(_collect(session,timeout=3.0));
        assert b"GOT:1b4f41" in bytes(captured).replace(b"\r",b"");
        assert session.wait(timeout=2.0)==0;
    finally: session.close();


@pytest.mark.skipif(os.name!="posix",reason="POSIX PTY test")
def test_sumedit_tui_accepts_sumterminal_cursor_and_alt_f3_sequences(tmp_path):
    from sumterminal.input import TerminalInputEncoder;
    from sumterminal.screen import TerminalScreen;
    path=tmp_path/"sample.txt"; path.write_text("alpha\nbeta\ngamma\n",encoding="utf-8");
    pythonpath=os.pathsep.join(os.path.abspath(value or os.getcwd()) for value in sys.path);
    session=TerminalSession(command=[sys.executable,"-m","sumtui.tools.edit",str(path)],cwd=str(tmp_path),env={"PYTHONPATH":pythonpath},rows=30,columns=100).start(); screen=TerminalScreen(30,100); encoder=TerminalInputEncoder(screen.modes); raw=bytearray();
    try:
        deadline=time.monotonic()+2.0;
        while time.monotonic()<deadline and b"\x1b[?1049h" not in raw:
            ready,_,_=select.select([session.fileno],[],[],0.05);
            if ready:
                event=session.read_event(65536);
                if event is not None and event.kind=="output": raw.extend(event.raw); screen.feed(event.text);
        assert session.poll() is None;
        assert b"\x1b[>27u" in raw;
        assert b"\x1b[?1049h" in raw;
        session.write(encoder.encode_key("right")); session.write(encoder.encode_key("down"));
        deadline=time.monotonic()+0.5;
        while time.monotonic()<deadline:
            ready,_,_=select.select([session.fileno],[],[],0.05);
            if ready:
                event=session.read_event(65536);
                if event is not None and event.kind=="output": screen.feed(event.text);
        session.write(encoder.encode_key("f3",alt=True));
        deadline=time.monotonic()+3.0;
        while time.monotonic()<deadline and session.poll() is None:
            ready,_,_=select.select([session.fileno],[],[],0.05);
            if ready: session.read_event(65536);
        assert session.poll()==0;
    finally:
        if session.poll() is None: session.terminate();
        try: session.wait(timeout=1.0);
        except Exception: pass;
        session.close();


def test_terminal_screen_revision_changes_only_when_screen_state_is_touched():
    from sumterminal.screen import TerminalScreen;
    screen=TerminalScreen(2,4); base=screen.revision;
    screen.feed("");
    assert screen.revision==base;
    screen.feed("x");
    assert screen.revision==base+1;
    value=screen.revision; screen.resize(2,4); assert screen.revision==value;
    screen.resize(3,4); assert screen.revision==value+1;


def test_cli_trace_input_option_is_parsed():
    from sumterminal.cli import parser;
    args=parser().parse_args(["--trace-input","--gui"]);
    assert args.trace_input is True;


def test_gui_key_trace_reports_application_mode_and_encoded_bytes(capsys):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    fake=SimpleNamespace(KMOD_CTRL=1,KMOD_SHIFT=2,KMOD_ALT=4,KMOD_GUI=8,K_F12=10,K_COMMA=11,K_t=12,K_RETURN=13,K_BACKSPACE=14,K_TAB=15,K_ESCAPE=16,K_UP=17,K_DOWN=18,K_RIGHT=19,K_LEFT=20,K_HOME=21,K_END=22,K_PAGEUP=23,K_PAGEDOWN=24,K_INSERT=25,K_DELETE=26,K_F1=27,K_F2=28,K_F3=29,K_F4=30,K_F5=31,K_F6=32,K_F7=33,K_F8=34,K_F9=35,K_F10=36,K_F11=37,K_SPACE=38,key=SimpleNamespace(name=lambda value:"up"));
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=TerminalPreferences(),trace_input=True); view.screen_model.feed("\x1b[?1h");
    event=SimpleNamespace(key=17,mod=0,unicode="");
    assert view._key_bytes(fake,event)==b"\x1bOA";
    trace=capsys.readouterr().err;
    assert "app_cursor=True" in trace;
    assert "send=1b 4f 41" in trace;


def test_set_visible_is_noop_when_visibility_does_not_change(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=TerminalPreferences());
    monkeypatch.setattr(view,"_sdl_window",lambda:(_ for _ in ()).throw(AssertionError("native SDL window should not be touched")));
    view.visible=True; view._set_visible(True); assert view.visible is True;


def test_font_metrics_reserve_space_for_bold_glyphs():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    class FakeFont:
        def __init__(self,bold=False): self.bold=bold;
        def size(self,text): return ((9 if self.bold else 8)*len(text),16);
        def get_linesize(self): return 18;
        def get_height(self): return 16;
    class FontAPI:
        @staticmethod
        def match_font(name,bold=False): return None;
        @staticmethod
        def SysFont(name,size,bold=False): return FakeFont(bold);
        @staticmethod
        def Font(path,size): return FakeFont(False);
    fake=SimpleNamespace(font=FontAPI()); prefs=TerminalPreferences(); prefs.general.font_name="mono"; session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs); view._make_fonts(fake); assert view.cell_width==9;


def test_gui_scrollback_view_uses_saved_primary_history():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(3,4)); view=GuiTerminalView(session,preferences=TerminalPreferences()); screen=view.screen_model;
    screen.feed("a\r\nb\r\nc\r\nd");
    assert screen.text_lines()==["b","c","d"];
    assert ["".join(cell.char for cell in line).rstrip() for line in screen.scrollback]==["a"];
    assert view._scroll_view(1)==1;
    assert ["".join(cell.char for cell in line).rstrip() for line in view._viewport_lines()]==["a","b","c"];
    assert view._scroll_view(-1)==0;
    assert ["".join(cell.char for cell in line).rstrip() for line in view._viewport_lines()]==["b","c","d"];


def test_gui_scrollback_is_disabled_while_alternate_screen_is_active():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(3,4)); view=GuiTerminalView(session,preferences=TerminalPreferences()); screen=view.screen_model;
    screen.feed("a\r\nb\r\nc\r\nd"); assert len(screen.scrollback)==1;
    screen.feed("\x1b[?1049h");
    assert view._scroll_view(10)==0;
    assert view.active_tab.scroll_offset==0;


def test_gui_shift_page_keys_scroll_history_without_writing_to_pty():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    fake=SimpleNamespace(KMOD_CTRL=1,KMOD_SHIFT=2,KMOD_ALT=4,KMOD_GUI=8,K_F12=10,K_COMMA=11,K_t=12,K_RETURN=13,K_BACKSPACE=14,K_TAB=15,K_ESCAPE=16,K_UP=17,K_DOWN=18,K_RIGHT=19,K_LEFT=20,K_HOME=21,K_END=22,K_PAGEUP=23,K_PAGEDOWN=24,K_INSERT=25,K_DELETE=26,K_F1=27,K_F2=28,K_F3=29,K_F4=30,K_F5=31,K_F6=32,K_F7=33,K_F8=34,K_F9=35,K_F10=36,K_F11=37,K_SPACE=38,key=SimpleNamespace(name=lambda value:"page up"));
    session=SimpleNamespace(size=TerminalSize(3,4)); view=GuiTerminalView(session,preferences=TerminalPreferences()); view.screen_model.feed("a\r\nb\r\nc\r\nd");
    event=SimpleNamespace(key=23,mod=2,unicode=""); assert view._key_bytes(fake,event)==b""; assert view.active_tab.scroll_offset==1;


def test_gui_runtime_error_is_recorded_without_stopping_view(monkeypatch,tmp_path):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    target=tmp_path/"crash.log";
    monkeypatch.setattr("sumterminal.gui.log_exception",lambda context,exc:target);
    session=SimpleNamespace(size=TerminalSize(24,80));
    view=GuiTerminalView(session,preferences=TerminalPreferences());
    view.running=True;
    assert view._record_runtime_error("test stage",ValueError("boom")) is False;
    assert view.running is True;
    assert view._runtime_error==("ValueError","boom");
    assert view._runtime_error_context=="test stage";
    assert view._runtime_error_log==str(target);
    assert view._force_redraw is True;


def test_gui_escape_dismisses_runtime_error(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(24,80));
    view=GuiTerminalView(session,preferences=TerminalPreferences());
    view._runtime_error=("RuntimeError","boom");
    view._runtime_error_context="renderer";
    fake_pygame=SimpleNamespace(KEYDOWN=10,K_ESCAPE=27);
    event=SimpleNamespace(type=10,key=27);
    assert view._handle_pygame_event(fake_pygame,event) is True;
    assert view._runtime_error is None;


@pytest.mark.skipif(os.name!="posix",reason="POSIX crash signal semantics")
def test_gui_supervisor_restarts_after_sigsegv_only(monkeypatch):
    import signal;
    from sumterminal import cli;
    calls=[];
    values=[-int(signal.SIGSEGV),0];
    monkeypatch.setattr(cli.subprocess,"call",lambda command:calls.append(tuple(command)) or values.pop(0));
    monkeypatch.setattr(cli.time,"monotonic",lambda:1.0);
    monkeypatch.setattr(cli.time,"sleep",lambda _value:None);
    monkeypatch.setattr(cli,"log_message",lambda _message:None);
    assert cli._supervise_gui(["--gui"])==0;
    assert len(calls)==2;
    assert "--_worker" in calls[0];
    assert cli._fatal_native_returncode(-int(signal.SIGSEGV)) is True;
    assert cli._fatal_native_returncode(-int(signal.SIGTERM)) is False;


def test_cli_print_crash_log(capsys):
    from sumterminal import cli;
    assert cli.main(["--print-crash-log"])==0;
    assert capsys.readouterr().out.strip().endswith("crash.log");


def test_terminal_selection_copy_text_trims_right_padding():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    session=SimpleNamespace(size=TerminalSize(3,8));
    view=GuiTerminalView(session,preferences=TerminalPreferences());
    view.screen_model.feed("alpha   \r\nbeta    ");
    tab=view.active_tab;
    tab.selection_anchor=(0,0);
    tab.selection_head=(1,7);
    assert view._selected_text(tab) == "alpha\nbeta";


def test_terminal_bracketed_paste_wraps_clipboard_text():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    written=[];
    session=SimpleNamespace(size=TerminalSize(3,8),write=lambda data:written.append(data));
    view=GuiTerminalView(session,preferences=TerminalPreferences());
    view.running=True;
    view.screen_model.bracketed_paste=True;
    assert view._paste_bytes("hello");
    assert written == [b"\x1b[200~hello\x1b[201~"];



def _fake_pygame_for_input(modifiers=0):
    from types import SimpleNamespace;
    names=("K_RETURN","K_BACKSPACE","K_TAB","K_ESCAPE","K_UP","K_DOWN","K_RIGHT","K_LEFT","K_HOME","K_END","K_PAGEUP","K_PAGEDOWN","K_INSERT","K_DELETE","K_F1","K_F2","K_F3","K_F4","K_F5","K_F6","K_F7","K_F8","K_F9","K_F10","K_F11","K_F12","K_SPACE","K_COMMA","K_c","K_v","K_t");
    values={name:index+100 for index,name in enumerate(names)};
    key_api=SimpleNamespace(get_mods=lambda:modifiers,name=lambda key:"," if key==values["K_COMMA"] else ".");
    return SimpleNamespace(KEYDOWN=1,KEYUP=9,QUIT=2,VIDEORESIZE=3,MOUSEWHEEL=4,MOUSEBUTTONDOWN=5,MOUSEBUTTONUP=6,MOUSEMOTION=7,TEXTINPUT=8,KMOD_SHIFT=1,KMOD_CTRL=2,KMOD_LALT=4,KMOD_RALT=8,KMOD_ALT=12,KMOD_MODE=16,KMOD_GUI=32,K_RALT=901,K_MODE=902,key=key_api,**values);


def test_altgr_printable_key_does_not_trigger_ctrl_shortcut(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    modifiers=2|8|16; pygame=_fake_pygame_for_input(modifiers);
    session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=TerminalPreferences()); calls=[];
    monkeypatch.setattr(view,"_open_preferences",lambda:calls.append(True));
    event=SimpleNamespace(key=pygame.K_COMMA,mod=modifiers,unicode="<");
    assert view._key_bytes(pygame,event) == b"";
    assert calls == [];


def test_shift_altgr_textinput_reaches_pty():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    modifiers=1|2|8|16; pygame=_fake_pygame_for_input(modifiers);
    written=[]; session=SimpleNamespace(size=TerminalSize(24,80),write=lambda data:written.append(data)); view=GuiTerminalView(session,preferences=TerminalPreferences()); view.running=True;
    event=SimpleNamespace(type=pygame.TEXTINPUT,text="÷");
    assert view._handle_pygame_event(pygame,event) is True;
    assert written == ["÷".encode("utf-8")];


def test_right_click_is_forwarded_to_mouse_tracking_child(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    pygame=_fake_pygame_for_input(0);
    written=[]; session=SimpleNamespace(size=TerminalSize(24,80),write=lambda data:written.append(data)); view=GuiTerminalView(session,preferences=TerminalPreferences()); view.running=True;
    view.screen_model.feed("\x1b[?1002h\x1b[?1006h");
    event=SimpleNamespace(type=pygame.MOUSEBUTTONDOWN,button=3,pos=(8,view.header_height+8));
    assert view._handle_pygame_event(pygame,event) is True;
    assert written and written[-1].startswith(b"\x1b[<2;");
    assert view._context_menu_open is False;


def test_shift_right_click_forces_terminal_context_menu(monkeypatch):
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    pygame=_fake_pygame_for_input(1);
    written=[]; session=SimpleNamespace(size=TerminalSize(24,80),write=lambda data:written.append(data)); view=GuiTerminalView(session,preferences=TerminalPreferences()); view.running=True;
    view.screen_model.feed("\x1b[?1002h\x1b[?1006h");
    monkeypatch.setattr(view,"_terminal_context_items",lambda:[("Copy",lambda:True,False)]);
    event=SimpleNamespace(type=pygame.MOUSEBUTTONDOWN,button=3,pos=(8,view.header_height+8));
    assert view._handle_pygame_event(pygame,event) is True;
    assert view._context_menu_open is True;
    assert written == [];


def test_right_alt_is_altgr_even_without_kmod_mode():
    from types import SimpleNamespace;
    from sumui.keyboard import pygame_modifier_state;
    modifiers=2|8; pygame=_fake_pygame_for_input(modifiers);
    state=pygame_modifier_state(modifiers,pygame);
    assert state["altgr"] is True;
    assert state["right_alt"] is True;
    assert state["alt"] is False;
    assert state["ctrl"] is False;


def test_physical_right_alt_keeps_textinput_working_when_sdl_reports_ctrl_alt():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    modifiers=2|4; pygame=_fake_pygame_for_input(modifiers);
    pygame.key.name=lambda key:"right alt" if key==pygame.K_RALT else ".";
    written=[]; session=SimpleNamespace(size=TerminalSize(24,80),write=lambda data:written.append(data));
    view=GuiTerminalView(session,preferences=TerminalPreferences()); view.running=True;
    down=SimpleNamespace(type=pygame.KEYDOWN,key=pygame.K_RALT,mod=modifiers,unicode="");
    assert view._handle_pygame_event(pygame,down) is True;
    assert view._altgr_down is True;
    text=SimpleNamespace(type=pygame.TEXTINPUT,text="Σ");
    assert view._handle_pygame_event(pygame,text) is True;
    assert written == ["Σ".encode("utf-8")];
    up=SimpleNamespace(type=pygame.KEYUP,key=pygame.K_RALT,mod=0,unicode="");
    assert view._handle_pygame_event(pygame,up) is True;
    assert view._altgr_down is False;


def test_physical_right_alt_shift_level4_text_reaches_pty():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    modifiers=1|2|4; pygame=_fake_pygame_for_input(modifiers);
    pygame.key.name=lambda key:"right alt" if key==pygame.K_RALT else ".";
    written=[]; session=SimpleNamespace(size=TerminalSize(24,80),write=lambda data:written.append(data));
    view=GuiTerminalView(session,preferences=TerminalPreferences()); view.running=True;
    view._handle_pygame_event(pygame,SimpleNamespace(type=pygame.KEYDOWN,key=pygame.K_RALT,mod=modifiers,unicode=""));
    view._handle_pygame_event(pygame,SimpleNamespace(type=pygame.TEXTINPUT,text="÷"));
    assert written == ["÷".encode("utf-8")];


def test_preferences_persist_font_modifiers(tmp_path):
    from sumterminal.config import TerminalPreferences, load_preferences, save_preferences;
    path=tmp_path/"terminal.toml"; value=TerminalPreferences(); value.general.font_name="mono"; value.general.font_bold=True; value.general.font_italic=True; value.general.font_small_caps=True; save_preferences(value,path); loaded=load_preferences(path);
    assert loaded.general.font_name=="mono";
    assert loaded.general.font_bold is True;
    assert loaded.general.font_italic is True;
    assert loaded.general.font_small_caps is True;


def test_small_caps_maps_lowercase_to_smaller_uppercase_renderer():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    prefs=TerminalPreferences(); prefs.general.font_small_caps=True; session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs);
    normal=object(); bold=object(); small=object(); small_bold=object(); view.font=normal; view.bold_font=bold; view.small_font=small; view.small_bold_font=small_bold;
    renderer,glyph,is_small=view._glyph_for_cell("a",False); assert renderer is small; assert glyph=="A"; assert is_small is True;
    renderer,glyph,is_small=view._glyph_for_cell("σ",True); assert renderer is small_bold; assert glyph=="Σ"; assert is_small is True;
    renderer,glyph,is_small=view._glyph_for_cell("A",False); assert renderer is normal; assert glyph=="A"; assert is_small is False;


def test_font_preferences_request_bold_and_italic_faces():
    from types import SimpleNamespace;
    from sumterminal.config import TerminalPreferences;
    from sumterminal.gui import GuiTerminalView;
    calls=[];
    class FakeFont:
        def __init__(self,name,size,bold=False,italic=False): self.name=name; self._size=size; self.bold=bold; self.italic=italic;
        def size(self,text): return (8*len(text),16);
        def get_linesize(self): return 18;
        def get_height(self): return 16;
    class FontAPI:
        @staticmethod
        def SysFont(name,size,bold=False,italic=False): calls.append((name,size,bold,italic)); return FakeFont(name,size,bold,italic);
        @staticmethod
        def Font(path,size): return FakeFont(path,size);
    fake=SimpleNamespace(font=FontAPI()); prefs=TerminalPreferences(); prefs.general.font_name="mono"; prefs.general.font_bold=True; prefs.general.font_italic=True; session=SimpleNamespace(size=TerminalSize(24,80)); view=GuiTerminalView(session,preferences=prefs); view._make_fonts(fake);
    assert calls[0][2:] == (True,True);
    assert view.font.bold is True; assert view.font.italic is True;


def test_preferences_migrate_incomplete_shortcut_without_losing_other_settings(tmp_path):
    from sumterminal.config import load_preferences;
    path=tmp_path/"terminal.toml";
    path.write_text('[general]\nfont_name = "DejaVu Sans Mono"\nfont_size = 21\n\n[dropdown]\nshortcut = "Press shortcut..."\nheight = 61\n',encoding="utf-8");
    loaded=load_preferences(path);
    assert loaded.dropdown.shortcut=="Ctrl+F12";
    assert loaded.dropdown.height==61;
    assert loaded.general.font_name=="DejaVu Sans Mono";
    assert loaded.general.font_size==21;

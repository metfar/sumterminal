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
    assert "sumterminal 0.1.0a3" in capsys.readouterr().out;


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

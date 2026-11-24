# Copyright (C) 2022 - 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


"""Client-side handling of paths reported by a Mechanical server on another platform."""

from pathlib import Path
from unittest.mock import PropertyMock, patch

import pytest

from ansys.mechanical.core.mechanical import Mechanical, _server_path

WINDOWS = {
    "project_dir": "C:\\work\\Proj_Mech_Files\\",
    "files": [
        "C:\\work\\Proj_Mech_Files\\StaticStructural\\file.rst",
        "C:\\work\\Proj_Mech_Files\\StaticStructural\\solve.out",
        "C:\\work\\Proj.mechdb",
    ],
}
POSIX = {
    "project_dir": "/work/Proj_Mech_Files/",
    "files": [
        "/work/Proj_Mech_Files/StaticStructural/file.rst",
        "/work/Proj_Mech_Files/StaticStructural/solve.out",
        "/work/Proj.mechdb",
    ],
}
EXPECTED = [
    ("Proj_Mech_Files", "StaticStructural", "file.rst"),
    ("Proj_Mech_Files", "StaticStructural", "solve.out"),
    ("Proj.mechdb",),
]


def _offline_mechanical(server):
    """Create a Mechanical client object whose server calls are replaced by fakes."""
    mechanical = Mechanical.__new__(Mechanical)
    mechanical._local = False
    mechanical._busy = False
    downloaded = []

    def fake_download(remote, out_file_name, chunk_size=None, progress_bar=None):
        downloaded.append(out_file_name)
        return out_file_name

    patches = [
        patch.object(Mechanical, "verify_valid_connection", lambda self: None),
        patch.object(Mechanical, "_get_files", lambda self, files, recursive=False: [files]),
        patch.object(Mechanical, "_download", lambda self, f, **kw: fake_download(f, **kw)),
        patch.object(Mechanical, "list_files", lambda self: list(server["files"])),
        patch.object(
            Mechanical,
            "project_directory",
            new_callable=PropertyMock,
            return_value=server["project_dir"],
        ),
    ]
    return mechanical, downloaded, patches


@pytest.mark.remote_session_launch
@pytest.mark.parametrize(
    "path, flavor, name",
    [
        ("C:\\work\\Proj_Mech_Files\\file.rst", "PureWindowsPath", "file.rst"),
        ("C:/work/file.rst", "PureWindowsPath", "file.rst"),
        ("/work/Proj_Mech_Files/file.rst", "PurePosixPath", "file.rst"),
    ],
)
def test_server_path_flavor(path, flavor, name):
    """Server paths are parsed with the server's flavor, not the client's."""
    assert type(_server_path(path)).__name__ == flavor
    assert _server_path(path).name == name


@pytest.mark.remote_session_launch
@pytest.mark.parametrize("server", [WINDOWS, POSIX], ids=["windows-server", "posix-server"])
def test_download_uses_file_name_only(server, tmp_path, monkeypatch):
    """download() writes <target_dir>/<file name>, whatever the server platform."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    mechanical, downloaded, patches = _offline_mechanical(server)
    for p in patches:
        p.start()
    try:
        out = mechanical.download(server["files"][0], target_dir=str(tmp_path / "dl"))
    finally:
        for p in patches:
            p.stop()
    assert out == [str(tmp_path / "dl" / "file.rst")]
    assert list(cwd.iterdir()) == []


@pytest.mark.remote_session_launch
@pytest.mark.parametrize("server", [WINDOWS, POSIX], ids=["windows-server", "posix-server"])
def test_download_project_keeps_hierarchy_under_target(server, tmp_path, monkeypatch):
    """download_project() mirrors the server layout under target_dir and nowhere else."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    target = tmp_path / "proj"
    mechanical, downloaded, patches = _offline_mechanical(server)
    for p in patches:
        p.start()
    try:
        out = mechanical.download_project(target_dir=str(target))
    finally:
        for p in patches:
            p.stop()
    assert out == [str(target.joinpath(*parts)) for parts in EXPECTED]
    assert list(cwd.iterdir()) == []
    assert all(Path(p).is_relative_to(target) for p in out)

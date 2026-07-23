from __future__ import annotations

from pathlib import Path

import pytest

from services.prompt_loader import PromptLoadError, load_prompt


def test_load_prompt_valid_utf8(tmp_path: Path):
    (tmp_path / "prompt.txt").write_text("Diagnóstico con acento.", encoding="utf-8")

    assert load_prompt("prompt.txt", base_dir=tmp_path) == "Diagnóstico con acento."


def test_load_prompt_empty_file_fails(tmp_path: Path):
    (tmp_path / "empty.txt").write_text("   \n", encoding="utf-8")

    with pytest.raises(PromptLoadError):
        load_prompt("empty.txt", base_dir=tmp_path)


def test_load_prompt_missing_file_fails(tmp_path: Path):
    with pytest.raises(PromptLoadError):
        load_prompt("missing.txt", base_dir=tmp_path)


@pytest.mark.parametrize("filename", ["../secret.txt", "nested/prompt.txt"])
def test_load_prompt_path_traversal_or_nested_path_fails(tmp_path: Path, filename):
    with pytest.raises(PromptLoadError):
        load_prompt(filename, base_dir=tmp_path)


def test_load_prompt_absolute_path_fails(tmp_path: Path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Contenido.", encoding="utf-8")

    with pytest.raises(PromptLoadError):
        load_prompt(str(prompt_path), base_dir=tmp_path)


def test_load_prompt_outside_directory_fails(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("Contenido.", encoding="utf-8")

    with pytest.raises(PromptLoadError):
        load_prompt("../outside.txt", base_dir=allowed)

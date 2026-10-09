"""Verifica exclusão entre processos e recuperação após encerramento."""
import os
import subprocess
import sys
import uuid

import pytest

from src.utils.single_instance import SingleInstance

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Mutex do Windows")


def probe(name):
    result = subprocess.run([sys.executable, "-c",
        "import sys; from src.utils.single_instance import SingleInstance; "
        "g=SingleInstance(sys.argv[1]); print(int(g.acquired)); g.close()", name],
        capture_output=True, text=True, timeout=10, check=True)
    return result.stdout.strip() == "1"


def test_blocks_other_process_and_allows_reopen():
    name = "Local\\RadarTest_" + uuid.uuid4().hex
    guard = SingleInstance(name)
    try:
        assert guard.acquired
        assert not probe(name)
        assert not probe(name)
    finally:
        guard.close()
    guard.close()
    assert probe(name)


def test_recovers_after_process_crash():
    name = "Local\\RadarTest_" + uuid.uuid4().hex
    child = subprocess.Popen([sys.executable, "-c",
        "import sys,time; from src.utils.single_instance import SingleInstance; "
        "g=SingleInstance(sys.argv[1]); print(int(g.acquired),flush=True); time.sleep(30)", name],
        stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "1"
        assert not probe(name)
    finally:
        child.kill()
        child.wait(timeout=10)
        child.stdout.close()
    assert probe(name)

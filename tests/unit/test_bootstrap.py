"""Unit tests for amifuse.bootstrap module."""

import inspect
import pytest


class TestAllocMsgport:
    """Verify alloc_msgport() initializes mp_MsgList correctly.

    Source inspection tests: fragile by design, to be replaced with
    functional tests when integration test infrastructure is available (Phase 5).
    """

    def test_alloc_msgport_empty_list_uses_sentinel_pointers(self):
        """Verify mp_MsgList is initialized as a proper empty Exec list."""
        from amifuse.bootstrap import BootstrapAllocator
        source = inspect.getsource(BootstrapAllocator.alloc_msgport)
        assert "lst.head.aptr = lh_tail_addr" in source
        assert "lst.tail_pred.aptr = lh_head_addr" in source
        assert "lst.head.aptr = 0" not in source

    def test_alloc_msgport_list_init_matches_init_msgport(self):
        """Verify alloc_msgport list init matches _init_msgport pattern."""
        from amifuse.startup_runner import HandlerLauncher
        from amifuse.bootstrap import BootstrapAllocator
        bootstrap_src = inspect.getsource(BootstrapAllocator.alloc_msgport)
        launcher_src = inspect.getsource(HandlerLauncher._init_msgport)
        assert "lst.tail.aptr = 0" in bootstrap_src
        assert "lst.tail.aptr = 0" in launcher_src
        assert "lst.head.aptr = 0" not in bootstrap_src
        assert "lst.head.aptr = 0" not in launcher_src

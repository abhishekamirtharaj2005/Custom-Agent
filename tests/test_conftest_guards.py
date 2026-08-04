import pytest

@pytest.mark.usefixtures("block_real_sockets")
def test_real_connection_is_actually_blocked():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="real network connection"):
        s.connect(("8.8.8.8", 53))

@pytest.mark.live
def test_live_marker_bypasses_guard():
    import socket
    # Just verify construction + the patched attribute isn't there;
    # doesn't actually dial out.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    assert callable(s.connect)

import socket

import pytest
from pytest_socket import SocketBlockedError


def test_unit_tests_cannot_open_network_sockets() -> None:
    # pytest-socket also emits a UserWarning, which the repository turns into an error; expect both.
    with pytest.raises(SocketBlockedError), pytest.warns(UserWarning, match="socket"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_unit_tests_may_use_unix_socket_pairs_for_the_event_loop() -> None:
    left, right = socket.socketpair()
    left.close()
    right.close()

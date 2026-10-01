from lelab.utils.connection_errors import explain_recording_error


def motor_error(port: str, found: str = "{}") -> RuntimeError:
    return RuntimeError(
        f"FeetechMotorsBus motor check failed on port '{port}':\n"
        "Missing motor IDs:\n  - 1 (expected model: 777)\n"
        "Full found motor list (id: model_number):\n" + found
    )


def test_identifies_leader_without_suggesting_motor_reconfiguration():
    message = explain_recording_error(motor_error("/dev/leader"), "/dev/leader", "/dev/follower")
    assert "leader arm" in message
    assert "separate power supply" in message
    assert "first motor" in message
    assert "follower arm" not in message


def test_identifies_follower():
    message = explain_recording_error(motor_error("/dev/follower"), "/dev/leader", "/dev/follower")
    assert "follower arm" in message


def test_keeps_partial_motor_failure_details():
    error = motor_error("/dev/leader", "{1: 777}")
    assert explain_recording_error(error, "/dev/leader", "/dev/follower") == str(error)


def test_keeps_unknown_connection_and_other_errors():
    for error in (motor_error("/dev/other"), RuntimeError("Video encoding failed")):
        assert explain_recording_error(error, "/dev/leader", "/dev/follower") == str(error)

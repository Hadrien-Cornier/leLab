"""Short, actionable messages for known connection failures.

The recording worker logs the original exception with its traceback.
These messages only change what the recording screen displays.
"""


def explain_recording_error(error: Exception, leader_port: str, follower_port: str) -> str:
    message = str(error)
    empty_motor_list = "Full found motor list (id: model_number):\n{}"
    if empty_motor_list not in message:
        return message

    for role, port in (("leader", leader_port), ("follower", follower_port)):
        check_failed = f"FeetechMotorsBus motor check failed on port '{port}':"
        if check_failed in message:
            return (
                f"The {role} arm's USB port opened, but none of its motors replied. "
                "Check the arm's separate power supply and the cable from its USB controller "
                "to the first motor. USB alone does not power the motors. "
                f"Port: {port}."
            )
    return message

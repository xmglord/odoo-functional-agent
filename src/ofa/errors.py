"""Exit codes and the exception hierarchy shared by all commands."""

OK = 0
FUNCTIONAL_FAILURE = 1
USAGE = 2
GUARD = 3
ENVIRONMENT = 4


class OfaError(Exception):
    """Base error. cli.main prints `ofa: <code>: <message>` and returns exit_code.

    <code> is the error's symbolic code when it has one (GuardError, EnvError,
    ValidationError), otherwise the numeric exit code.
    """

    exit_code = FUNCTIONAL_FAILURE
    code = None

    def __init__(self, msg, exit_code=None):
        super().__init__(msg)
        self.msg = msg
        if exit_code is not None:
            self.exit_code = exit_code

    @property
    def label(self):
        return self.code or str(self.exit_code)


class UsageError(OfaError):
    exit_code = USAGE

    def __init__(self, msg):
        super().__init__(msg)


class ValidationError(OfaError):
    exit_code = USAGE

    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code


class GuardError(OfaError):
    exit_code = GUARD

    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code


class OdooError(OfaError):
    exit_code = ENVIRONMENT

    def __init__(self, status, name, message):
        super().__init__(f"{name}: {message}" if name else message)
        self.status = status
        self.name = name
        self.message = message


class EnvError(OfaError):
    exit_code = ENVIRONMENT

    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code

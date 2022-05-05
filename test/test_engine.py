from typing import *
import traceback
import os
from inspect import getframeinfo, stack

__test_cases = []

class TestAssertionFailedException(Exception):
    def __init__(self, message: str):
        caller = getframeinfo(stack()[2][0])
        self.message = "in file {} line {} by {}(): {}".format(caller.filename, caller.lineno, caller.function, message)
        super().__init__(self, self.message)
    
    def __str__(self):
        return self.message

def test(test_method: Callable or Type) -> None:
    __test_cases.append(test_method)

def assert_true(val: bool):
    if not bool(val):
        raise TestAssertionFailedException("Expected value True but got False")

def assert_equal(val: Any, asserted: Any):
    if not val == asserted:
        raise TestAssertionFailedException("Expected value {} but got {}".format(repr(asserted), repr(val)))

def assert_type(val: Any, asserted: Type):
    if not isinstance(val, asserted):
        raise TestAssertionFailedException("Expected value {} but got type {}".format(asserted, type(val)))

def run_test():
    tests_passed = 0
    for i in range(len(__test_cases)):
        try:
            __test_cases[i]()
            tests_passed += 1
            os.write(1, b"\033[92m[OK]\033[0m")
            print("[Test {}/{} passed]".format(tests_passed, len(__test_cases)))
        except TestAssertionFailedException as e:
            os.write(1, b"\033[91m[ERROR]\033[0m")
            print("[Test {}/{} failed with assertion]".format(tests_passed, len(__test_cases)))
            os.write(1, b"\033[91m[ERROR]\033[0m")
            print(e)
        except Exception as e:
            e_str = traceback.format_exc()
            print(e_str.strip("\n"))
            os.write(1, b"\033[91m[ERROR]\033[0m")
            print("[Test {}/{} failed with exception]".format(tests_passed, len(__test_cases)))
            os.write(1, b"\033[91m[ERROR]\033[0m")
            print(e)
    if tests_passed == len(__test_cases):
        message = "great job!"
    elif tests_passed / len(__test_cases) >= 0.8 or (tests_passed + 1 == len(__test_cases) and len(__test_cases) > 1):
        message = "close one, you can do it!"
    else:
        message = "you can do this!"
    os.write(1, b"\033[94m[TESTS DONE]\033[0m")
    print("[{}/{} of tests passed - {}]".format(tests_passed, len(__test_cases), message))

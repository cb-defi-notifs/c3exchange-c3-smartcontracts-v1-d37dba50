"""
The XAssert facility to aid debugging.
"""

from inspect import currentframe

from pyteal import And, Assert, Int


# pylint: disable-next=invalid-name
def XAssert(cond, comment):
    """
    This method will emit a push of the assertion' line number so
    when an assertion is triggered, the opcode context of the failing assert
    can be looked upon  for the originating line. The comment string will
    appear on the output TEAL file for further context info.
    """
    return Assert(And(cond, Int(currentframe().f_back.f_lineno)), comment=comment)

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import torch
import numpy as np
import re
from enum import Enum, IntEnum

FP32_EXPONENT_BIAS = 127
FP32_MIN_NORMAL = 2 ** (-FP32_EXPONENT_BIAS + 1)

# Enum for rounding modes
class RoundingMode(IntEnum):
    nearest = 0
    floor = 1
    even = 2

    @staticmethod
    def string_enums():
        return [s.name for s in list(RoundingMode)]

# Enum for scalar data formats
class ElemFormat(Enum):
    int8 = 1
    int7 = 2
    int6 = 3
    int5 = 4
    int4 = 5
    int3 = 6
    int2 = 7
    fp8_e5m2 = 8
    fp8_e4m3 = 9
    fp6_e3m2 = 10
    fp6_e2m3 = 11
    fp5_e4m0 = 12
    fp5_e3m1 = 13
    fp5_e2m2 = 14
    fp5_e1m3 = 15
    fp4_e3m0 = 16
    fp4_e2m1 = 17
    fp4_e1m2 = 18
    fp3_e2m0 = 19
    fp3_e1m1 = 20
    fp4 = 17
    float16 = 22
    fp16 = 22
    bfloat16 = 23
    bf16 = 23

    @staticmethod
    def from_str(s):
        assert(s != None), "String elem_format == None"
        s = s.lower()
        return getattr(ElemFormat, s)


def _get_min_norm(ebits):
    """ Valid for all float formats """
    emin = 2 - (2 ** (ebits - 1))
    return 0 if ebits == 0 else 2 ** emin


def _get_max_norm(ebits, mbits):
    """ Valid only for floats that define NaN """
    assert(ebits >= 5), "invalid for floats that don't define NaN"
    emax = 0 if ebits==0 else 2**(ebits - 1) - 1
    return 2**emax * float(2**(mbits-1) - 1) / 2**(mbits-2)


_FORMAT_CACHE = {}
def _get_format_params(fmt):
    """ Allowed formats:
        - intX:         2 <= X <= 32, assume sign-magnitude, 1.xxx representation
        - floatX/fpX:   16 <= X <= 28, assume top exp is used for NaN/Inf
        - bfloatX/bfX:  9 <= X <= 32
        - fp4,                  no NaN/Inf
        - fp6_e3m2/e2m3,        no NaN/Inf 
        - fp8_e4m3/e5m2,        e5m2 normal NaN/Inf, e4m3 special behavior

        Returns:
          ebits: exponent bits
          mbits: mantissa bits: includes sign and implicit bits
          emax: max normal exponent
          max_norm: max normal number
          min_norm: min normal number
    """
    if type(fmt) is str:
        fmt = ElemFormat.from_str(fmt)

    if fmt in _FORMAT_CACHE:
        return _FORMAT_CACHE[fmt]

    if fmt == ElemFormat.int8:
        ebits, mbits = 0, 8
        emax = 0
    elif fmt == ElemFormat.int7:
        ebits, mbits = 0, 7
        emax = 0
    elif fmt == ElemFormat.int6:
        ebits, mbits = 0, 6
        emax = 0
    elif fmt == ElemFormat.int5:
        ebits, mbits = 0, 5
        emax = 0
    elif fmt == ElemFormat.int4:
        ebits, mbits = 0, 4
        emax = 0
    elif fmt == ElemFormat.int3:
        ebits, mbits = 0, 3
        emax = 0
    elif fmt == ElemFormat.int2:
        ebits, mbits = 0, 2
        emax = 0
    elif fmt == ElemFormat.fp8_e5m2:
        ebits, mbits = 5, 4
        emax = 2**(ebits - 1) - 1
    elif fmt == ElemFormat.fp8_e4m3:
        ebits, mbits = 4, 5
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp6_e3m2:
        ebits, mbits = 3, 4
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp6_e2m3:
        ebits, mbits = 2, 5
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp5_e4m0:
        ebits, mbits = 4, 2
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp5_e3m1:
        ebits, mbits = 3, 3
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp5_e2m2:
        ebits, mbits = 2, 4
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp5_e1m3:
        ebits, mbits = 1, 5
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp4_e3m0:
        ebits, mbits = 3, 2
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp4_e2m1:
        ebits, mbits = 2, 3
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp4_e1m2:
        ebits, mbits = 1, 4
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp3_e2m0:
        ebits, mbits = 2, 2
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.fp3_e1m1:
        ebits, mbits = 1, 3
        emax = 2**(ebits - 1)
    elif fmt == ElemFormat.float16:
        ebits, mbits = 5, 12
        emax = 2**(ebits - 1) - 1
    elif fmt == ElemFormat.bfloat16:
        ebits, mbits = 8, 9
        emax = 2**(ebits - 1) - 1
    else:
        raise Exception("Unknown element format %s" % fmt)
    
    if fmt != ElemFormat.fp8_e4m3:
        max_norm = 2**emax * float(2**(mbits-1) - 1) / 2**(mbits-2)
    else:
        max_norm = 2**emax * 1.75  # FP8 has custom max_norm

    min_norm = _get_min_norm(ebits)
    
    _FORMAT_CACHE[fmt] = (ebits, mbits, emax, max_norm, min_norm)

    return ebits, mbits, emax, max_norm, min_norm

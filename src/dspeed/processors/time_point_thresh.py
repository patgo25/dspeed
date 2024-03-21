from __future__ import annotations

import numpy as np
from numba import guvectorize

from ..errors import DSPFatal
from ..utils import numba_defaults_kwargs as nb_kwargs


@guvectorize(
    [
        "void(float32[:], float32, float32, float32, float32[:])",
        "void(float64[:], float64, float64, float64, float64[:])",
    ],
    "(n),(),(),()->()",
    **nb_kwargs,
)
def time_point_thresh(
    w_in: np.ndarray, a_threshold: float, t_start: int, walk_forward: int, t_out: float
) -> None:
    """Find the index where the waveform value crosses the threshold, walking
    either forward or backward from the starting index.

    Parameters
    ----------
    w_in
        the input waveform.
    a_threshold
        the threshold value.
    t_start
        the starting index.
    walk_forward
        the backward (``0``) or forward (``1``) search direction.
    t_out
        the index where the waveform value crosses the threshold.

    JSON Configuration Example
    --------------------------

    .. code-block :: json

        "tp_0": {
            "function": "time_point_thresh",
            "module": "dspeed.processors",
            "args": ["wf_atrap", "bl_std", "tp_start", 0, "tp_0"],
            "unit": "ns"
        }
    """
    t_out[0] = np.nan

    if (
        np.isnan(w_in).any()
        or np.isnan(a_threshold)
        or np.isnan(t_start)
        or np.isnan(walk_forward)
    ):
        return

    if np.floor(t_start) != t_start:
        raise DSPFatal("The starting index must be an integer")

    if np.floor(walk_forward) != walk_forward:
        raise DSPFatal("The search direction must be an integer")

    if int(t_start) < 0 or int(t_start) >= len(w_in):
        raise DSPFatal("The starting index is out of range")

    if int(walk_forward) == 1:
        for i in range(int(t_start), len(w_in) - 1, 1):
            if w_in[i] <= a_threshold < w_in[i + 1]:
                t_out[0] = i
                return
    else:
        for i in range(int(t_start), 0, -1):
            if w_in[i - 1] < a_threshold <= w_in[i]:
                t_out[0] = i
                return


@guvectorize(
    [
        "void(float32[:], float32, float32, int64, char, float32[:])",
        "void(float64[:], float64, float64, int64, char, float64[:])",
    ],
    "(n),(),(),(),()->()",
    **nb_kwargs,
)
def interpolated_time_point_thresh(
    w_in: np.ndarray,
    a_threshold: float,
    t_start: int,
    walk_forward: int,
    mode_in: np.int8,
    t_out: float,
) -> None:
    """Find the time where the waveform value crosses the threshold

    Search performed walking either forward or backward from the starting
    index. Use interpolation to estimate a time between samples. Interpolation
    mode selected with `mode_in`.

    Parameters
    ----------
    w_in
        the input waveform.
    a_threshold
        the threshold value.
    t_start
        the starting index.
    walk_forward
        the backward (``0``) or forward (``1``) search direction.
    mode_in
        Character selecting which interpolation method to use. Note this
        must be passed as a ``int8``, e.g. ``ord('i')``. Options:

        * ``i`` -- integer `t_in`; equivalent to
          :func:`~.dsp.processors.fixed_sample_pickoff`
        * ``b`` -- before; closest integer sample before threshold crossing
        * ``a`` -- after; closest integer sample after threshold crossing
        * ``r`` -- round; round to nearest integer sample to threshold crossing
        * ``l`` -- linear interpolation
        The following modes are meant to mirror the options
        dspeed.upsampler
        * ``f`` -- floor; interpolated values are at previous neighbor.
          Equivalent to ``a``
        * ``c`` -- ceiling, interpolated values are at next neighbor.
          Equivalent to ``b``
        * ``n`` -- nearest-neighbor interpolation; threshold crossing is
          half-way between samples
        * ``h`` -- Hermite cubic spline interpolation (*not implemented*)
        * ``s`` -- natural cubic spline interpolation (*not implemented*)
    t_out
        the index where the waveform value crosses the threshold.

    JSON Configuration Example
    --------------------------

    .. code-block :: json

        "tp_0": {
            "function": "time_point_thresh",
            "module": "dspeed.processors",
            "args": ["wf_atrap", "bl_std", "tp_start", 0, "'l'", "tp_0"],
            "unit": "ns"
        }
    """
    t_out[0] = np.nan

    if (
        np.isnan(w_in).any()
        or np.isnan(a_threshold)
        or np.isnan(t_start)
        or np.isnan(walk_forward)
    ):
        return

    if t_start < 0 or t_start >= len(w_in):
        return

    i_cross = -1
    if walk_forward > 0:
        for i in range(int(t_start), len(w_in) - 1, 1):
            if w_in[i] <= a_threshold < w_in[i + 1]:
                i_cross = i
                break
    else:
        for i in range(int(t_start), 1, -1):
            if w_in[i - 1] < a_threshold <= w_in[i]:
                i_cross = i - 1
                break

    if i_cross == -1:
        return

    if mode_in == ord("i"):  # return index before crossing
        t_out[0] = i_cross
    elif mode_in in (ord("a"), ord("f")):  # return index after crossing
        t_out[0] = i_cross + 1
    elif mode_in in (ord("b"), ord("c")):  # return index before crossing
        t_out[0] = i_cross
    elif mode_in == ord("r"):  # return closest index to crossing
        if abs(a_threshold - w_in[i_cross]) < abs(a_threshold - w_in[i_cross + 1]):
            t_out[0] = i_cross
        else:
            t_out[0] = i_cross + 1
    elif mode_in == ord("n"):  # nearest-neighbor; return half-way between samps
        t_out[0] = i_cross + 0.5
    elif mode_in == ord("l"):  # linear
        t_out[0] = i_cross + (a_threshold - w_in[i_cross]) / (
            w_in[i_cross + 1] - w_in[i_cross]
        )
    else:
        raise DSPFatal("Unrecognized interpolation mode")


@guvectorize(
    [
        "void(float32[:], float32[:], float32, float32, char, float32[:])",
        "void(float64[:], float64[:], float64, float64, char, float64[:])",
    ],
    "(n),(m),(),(),()->(m)",
    **nb_kwargs,
)
def multi_time_point_thresh(
    w_in: np.ndarray,
    a_threshold: np.ndarray,
    t_start: int,
    polarity: int,
    mode_in: np.int8,
    t_out: np.ndarray,
) -> None:
    """Find the time where the waveform value crosses the threshold

    Search performed walking either forward or backward from the starting
    index. Use interpolation to estimate a time between samples. Interpolation
    mode selected with `mode_in`.

    Parameters
    ----------
    w_in
        the input waveform.
    a_threshold
        list of threshold values.
    t_start
        the starting index.
    polarity
        is the average slope of the waveform up (>0) or down (<0) in the
        search region; only sign matters, not value. Raise Exception if 0.
    mode_in
        Character selecting which interpolation method to use. Note this
        must be passed as a ``int8``, e.g. ``ord('i')``. Options:

        * ``i`` -- integer `t_in`; equivalent to
          :func:`~.dsp.processors.fixed_sample_pickoff`
        * ``b`` -- before; closest integer sample before threshold crossing
        * ``a`` -- after; closest integer sample after threshold crossing
        * ``r`` -- round; round to nearest integer sample to threshold crossing
        * ``l`` -- linear interpolation
        The following modes are meant to mirror the options
        dspeed.upsampler
        * ``f`` -- floor; interpolated values are at previous neighbor.
          Equivalent to ``a``
        * ``c`` -- ceiling, interpolated values are at next neighbor.
          Equivalent to ``b``
        * ``n`` -- nearest-neighbor interpolation; threshold crossing is
          half-way between samples
        * ``h`` -- Hermite cubic spline interpolation (*not implemented*)
        * ``s`` -- natural cubic spline interpolation (*not implemented*)
    t_out
        the index where the waveform value crosses the threshold.

    JSON Configuration Example
    --------------------------

    .. code-block :: json

        "tp_0": {
            "function": "time_point_thresh",
            "module": "dspeed.processors",
            "args": ["wf_atrap", "bl_std", "tp_start", 0, "'l'", "tp_0"],
            "unit": "ns"
        }
    """
    t_out[:] = np.nan

    if np.isnan(w_in).any() or np.isnan(a_threshold).any() or np.isnan(t_start):
        return

    if t_start < 0 or t_start >= len(w_in):
        return

    # make polarity +/- 1
    if polarity > 0:
        polarity = 1
    elif polarity < 0:
        polarity = -1
    else:
        raise DSPFatal("polarity cannot be 0")

    sorted_idx = np.argsort(a_threshold)

    # Get initial values for search
    t_start = int(t_start)
    a_start = w_in[t_start]
    i_start = len(sorted_idx)
    for i in range(len(sorted_idx)):
        if a_threshold[sorted_idx[i]] >= a_start:
            i_start = i
            break

    # Search for timepoints at larger values
    i_tp = i_start
    if i_tp < len(sorted_idx):
        idx = sorted_idx[i_tp]
        for i_wf in range(t_start, len(w_in) - 1 if polarity > 0 else -1, polarity):
            if i_tp >= len(sorted_idx):
                break
            while w_in[i_wf] <= a_threshold[idx] < w_in[i_wf + polarity]:
                if mode_in == ord("i"):  # return index closest to start of search
                    t_out[idx] = i_wf
                elif mode_in in (ord("a"), ord("f")):  # return index after crossing
                    t_out[idx] = i_wf if polarity < 0 else i_wf + 1
                elif mode_in in (ord("b"), ord("c")):  # return index before crossing
                    t_out[idx] = i_wf if polarity > 0 else i_wf - 1
                elif mode_in == ord("r"):  # round; return closest index
                    if (
                        a_threshold[idx] - w_in[i_wf]
                        < w_in[i_wf + polarity] - a_threshold[sorted_idx[i_tp]]
                    ):
                        t_out[idx] = i_wf
                    else:
                        t_out[idx] = i_wf + polarity
                elif mode_in == ord(
                    "n"
                ):  # nearest-neighbor; return half-way between samps
                    t_out[idx] = i_wf + 0.5 * polarity
                elif mode_in == ord("l"):  # linear
                    t_out[idx] = i_wf + (a_threshold[idx] - w_in[i_wf]) / (
                        w_in[i_wf + polarity] - w_in[i_wf]
                    )
                else:
                    raise DSPFatal("Unrecognized interpolation mode")
                i_tp += 1
                if i_tp >= len(sorted_idx):
                    break
                idx = sorted_idx[i_tp]

    # Search for timepoints at smaller values
    i_tp = i_start - 1
    if i_tp >= 0:
        idx = sorted_idx[i_tp]
        for i_wf in range(
            t_start - 1, len(w_in) - 1 if polarity < 0 else -1, -polarity
        ):
            if i_tp < 0:
                break
            while w_in[i_wf] <= a_threshold[idx] < w_in[i_wf + polarity]:
                if mode_in == ord("i"):  # return index closest to start of search
                    t_out[idx] = i_wf
                elif mode_in in (ord("a"), ord("f")):  # return index after crossing
                    t_out[idx] = i_wf if polarity < 0 else i_wf + 1
                elif mode_in in (ord("b"), ord("c")):  # return index before crossing
                    t_out[idx] = i_wf if polarity > 0 else i_wf - 1
                elif mode_in == ord("r"):  # round; return closest index
                    if (
                        a_threshold[idx] - w_in[i_wf]
                        < w_in[i_wf + polarity] - a_threshold[idx]
                    ):
                        t_out[idx] = i_wf
                    else:
                        t_out[idx] = i_wf + polarity
                elif mode_in == ord(
                    "n"
                ):  # nearest-neighbor; return half-way between samps
                    t_out[idx] = i_wf + 0.5 * polarity
                elif mode_in == ord("l"):  # linear
                    t_out[idx] = i_wf + (a_threshold[idx] - w_in[i_wf]) / (
                        w_in[i_wf + polarity] - w_in[i_wf]
                    )
                else:
                    raise DSPFatal("Unrecognized interpolation mode")
                i_tp -= 1
                if i_tp < 0:
                    break
                idx = sorted_idx[i_tp]

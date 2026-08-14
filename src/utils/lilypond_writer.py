import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("LilyPondWriter")

# MIDI note number offsets for pitch classes
PITCH_CLASS_MAP = {
    'c': 0, 'cis': 1, 'cisis': 2, 'des': 1, 'deses': 0,
    'd': 2, 'dis': 3, 'disis': 4, 'es': 3, 'eses': 2,
    'e': 4, 'eis': 5, 'eisis': 6, 'fes': 4, 'feses': 3,
    'f': 5, 'fis': 6, 'fisis': 7, 'ges': 6, 'geses': 5,
    'g': 7, 'gis': 8, 'gisis': 9, 'as': 8, 'ases': 7,
    'a': 9, 'ais': 10, 'aisis': 11, 'bes': 10, 'beses': 9,
    'b': 11, 'bis': 12, 'bisis': 13, 'ces': 11, 'ceses': 10
}

# TPC (Tonal Pitch Class) map for MuseScore
TPC_MAP = {
    'ceses': 0, 'geses': 1, 'deses': 2, 'ases': 3, 'eses': 4, 'beses': 5, 'feses': 6,
    'ces': 7, 'ges': 8, 'des': 9, 'as': 10, 'es': 11, 'bes': 12, 'f': 13,
    'c': 14, 'g': 15, 'd': 16, 'a': 17, 'e': 18, 'b': 19, 'fis': 20,
    'cis': 21, 'gis': 22, 'dis': 23, 'ais': 24, 'eis': 25, 'bis': 26,
    'fisis': 27, 'cisis': 28, 'gisis': 29, 'disis': 30, 'aisis': 31, 'eisis': 32, 'bisis': 33
}


def parse_lilypond_pitch(pitch_str: str) -> Tuple[int, int]:
    """
    Parse an absolute LilyPond pitch string (e.g., c', fis'', bes,, g) into (midi_pitch, tpc).
    - c (no mark) = C3 (MIDI 48)
    - c' = C4 (MIDI 60)
    - c'' = C5 (MIDI 72)
    - c, = C2 (MIDI 36)
    """
    match = re.match(r"^([a-g](?:is|es|isis|eses)?)([,']*)$", pitch_str.strip())
    if not match:
        raise ValueError(f"Invalid LilyPond pitch: '{pitch_str}'")

    base_name = match.group(1)
    octave_marks = match.group(2)

    pc = PITCH_CLASS_MAP.get(base_name, 0)
    tpc = TPC_MAP.get(base_name, 14)

    # Base octave for no marks is octave 3 (C3 = 48)
    octave = 3
    for char in octave_marks:
        if char == "'":
            octave += 1
        elif char == ",":
            octave -= 1

    midi_pitch = (octave + 1) * 12 + pc
    midi_pitch = max(0, min(127, midi_pitch))
    return midi_pitch, tpc


def parse_lilypond_duration(dur_str: str) -> Tuple[Dict[str, int], int]:
    """
    Parse a duration string (e.g. '4', '2.', '8', '16..') into:
    1. Duration dict: {"numerator": num, "denominator": den}
    2. Duration ticks (based on 480 ticks per quarter note = 1920 per whole note)
    """
    match = re.match(r"^(\d+)(\.*)$", dur_str.strip())
    if not match:
        raise ValueError(f"Invalid LilyPond duration: '{dur_str}'")

    base_val = int(match.group(1))
    dots = len(match.group(2))

    # Whole note = 1920 ticks
    base_ticks = 1920 // base_val if base_val > 0 else 480
    total_ticks = base_ticks
    dot_add = base_ticks // 2
    for _ in range(dots):
        total_ticks += dot_add
        dot_add //= 2

    # Express as fraction of a whole note: total_ticks / 1920
    import math
    gcd = math.gcd(total_ticks, 1920)
    num = total_ticks // gcd
    den = 1920 // gcd

    return {"numerator": num, "denominator": den}, total_ticks


class MusicElement:
    """Represents a single note, rest, or chord in a voice."""
    def __init__(self, is_rest: bool = False):
        self.is_rest: bool = is_rest
        self.pitches: List[Tuple[int, int]] = []  # List of (midi_pitch, tpc)
        self.duration_dict: Dict[str, int] = {"numerator": 1, "denominator": 4}
        self.duration_ticks: int = 480
        self.measure: int = 1
        self.tick_in_measure: int = 0


def split_lilypond_voices(lily_code: str) -> List[str]:
    """
    Extract voices from LilyPond polyphonic syntax:
    - Handles << { voice1 } \\ { voice2 } >>
    - Handles << \new Voice { voice1 } \new Voice { voice2 } >>
    - Fallback: single voice code
    """
    cleaned = re.sub(r'%.*$', '', lily_code, flags=re.MULTILINE) # Remove comments
    cleaned = cleaned.strip()

    # Check for << ... >>
    if cleaned.startswith("<<") and cleaned.endswith(">>"):
        inner = cleaned[2:-2].strip()

        # Check for explicit \new Voice { ... }
        voice_matches = re.findall(r'(?:\\new\s+Voice(?:\s*=\s*"[^"]*")?\s*)?\{([^}]+)\}', inner)
        if len(voice_matches) > 1:
            return [v.strip() for v in voice_matches]

        # Check for double backslash separator \\
        if "\\\\" in inner:
            parts = inner.split("\\\\")
            # Clean braces from parts if present
            cleaned_parts = []
            for p in parts:
                p_clean = p.strip()
                if p_clean.startswith("{") and p_clean.endswith("}"):
                    p_clean = p_clean[1:-1].strip()
                cleaned_parts.append(p_clean)
            return cleaned_parts

    # Clean outer braces if single voice { ... }
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1].strip()

    return [cleaned]


def parse_voice_tokens(voice_code: str, start_measure: int = 1, time_sig_ticks: int = 1920) -> List[MusicElement]:
    """
    Parse a single voice string into a list of MusicElement objects.
    Tracks measures either by explicit '|' bar checks or by accumulating ticks.
    """
    elements: List[MusicElement] = []
    current_measure = start_measure
    current_tick_in_meas = 0
    last_duration_str = "4"

    # Regex token patterns
    token_regex = re.compile(
        r'(\|)'                                                    # Group 1: Bar check
        r'|(<[^>]+>(?:\d+\.*)?)'                                    # Group 2: Chord
        r'|([rs](\d+\.*)?)'                                         # Group 3: Rest, Group 4: Duration
        r'|(([a-g](?:is|es|isis|eses)?[\',]*)(\d+\.*)?)'            # Group 5: Note, Group 6: Pitch, Group 7: Duration
        r'|(\\\w+(?:\s+[^\s{}<>]+)?)'                              # Group 8: Directive (ignored)
    )

    tokens = token_regex.finditer(voice_code)

    for match in tokens:
        bar_check = match.group(1)
        chord_token = match.group(2)
        rest_token = match.group(3)
        note_token = match.group(5)

        if bar_check:
            # Bar check only forces new measure if we have unconsumed ticks in measure
            if current_tick_in_meas > 0:
                current_measure += 1
                current_tick_in_meas = 0
            continue

        if rest_token:
            dur_str = match.group(4) or last_duration_str
            last_duration_str = dur_str
            dur_dict, dur_ticks = parse_lilypond_duration(dur_str)

            elem = MusicElement(is_rest=True)
            elem.duration_dict = dur_dict
            elem.duration_ticks = dur_ticks
            elem.measure = current_measure
            elem.tick_in_measure = current_tick_in_meas
            elements.append(elem)

            current_tick_in_meas += dur_ticks
            if current_tick_in_meas >= time_sig_ticks:
                current_measure += current_tick_in_meas // time_sig_ticks
                current_tick_in_meas = current_tick_in_meas % time_sig_ticks
            continue

        if chord_token:
            # Parse chord <c' e' g'>4
            chord_match = re.match(r'<([^>]+)>(\d+\.*)?', chord_token)
            if chord_match:
                pitches_str = chord_match.group(1).split()
                dur_str = chord_match.group(2) or last_duration_str
                last_duration_str = dur_str
                dur_dict, dur_ticks = parse_lilypond_duration(dur_str)

                elem = MusicElement(is_rest=False)
                elem.duration_dict = dur_dict
                elem.duration_ticks = dur_ticks
                elem.measure = current_measure
                elem.tick_in_measure = current_tick_in_meas

                for p_str in pitches_str:
                    try:
                        midi_p, tpc_val = parse_lilypond_pitch(p_str)
                        elem.pitches.append((midi_p, tpc_val))
                    except Exception as e:
                        logger.warning(f"Error parsing chord pitch {p_str}: {e}")

                if elem.pitches:
                    elements.append(elem)
                    current_tick_in_meas += dur_ticks
                    if current_tick_in_meas >= time_sig_ticks:
                        current_measure += current_tick_in_meas // time_sig_ticks
                        current_tick_in_meas = current_tick_in_meas % time_sig_ticks
            continue

        if note_token:
            pitch_str = match.group(6)
            dur_str = match.group(7) or last_duration_str
            last_duration_str = dur_str
            dur_dict, dur_ticks = parse_lilypond_duration(dur_str)

            try:
                midi_p, tpc_val = parse_lilypond_pitch(pitch_str)
                elem = MusicElement(is_rest=False)
                elem.pitches.append((midi_p, tpc_val))
                elem.duration_dict = dur_dict
                elem.duration_ticks = dur_ticks
                elem.measure = current_measure
                elem.tick_in_measure = current_tick_in_meas
                elements.append(elem)

                current_tick_in_meas += dur_ticks
                if current_tick_in_meas >= time_sig_ticks:
                    current_measure += current_tick_in_meas // time_sig_ticks
                    current_tick_in_meas = current_tick_in_meas % time_sig_ticks
            except Exception as e:
                logger.warning(f"Error parsing note {pitch_str}: {e}")
            continue

    return elements


def lilypond_to_actions(
    lily_code: str,
    start_measure: int = 1,
    staff_idx: int = 0,
    time_sig_ticks: int = 1920
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Converts a LilyPond snippet into a structured list of MuseScore actions for processSequence.
    Guarantees strict voice ordering (Voice 0 first, then Voice 1, etc.) per measure.
    
    Returns:
    - actions: List of MuseScore command dicts (e.g. [{"action": "addNote", "params": {...}}])
    - max_measure_reached: The highest measure number referenced.
    """
    voice_strings = split_lilypond_voices(lily_code)
    
    # Parse all voices
    parsed_voices: Dict[int, List[MusicElement]] = {}
    max_measure = start_measure

    for v_idx, v_code in enumerate(voice_strings):
        parsed = parse_voice_tokens(v_code, start_measure=start_measure, time_sig_ticks=time_sig_ticks)
        parsed_voices[v_idx] = parsed
        for el in parsed:
            if el.measure > max_measure:
                max_measure = el.measure

    # Organize elements by Measure -> Voice -> Elements
    measures_map: Dict[int, Dict[int, List[MusicElement]]] = {}
    for m in range(start_measure, max_measure + 1):
        measures_map[m] = {}
        for v_idx in range(len(voice_strings)):
            measures_map[m][v_idx] = []

    for v_idx, elements in parsed_voices.items():
        for el in elements:
            if el.measure not in measures_map:
                measures_map[el.measure] = {}
            if v_idx not in measures_map[el.measure]:
                measures_map[el.measure][v_idx] = []
            measures_map[el.measure][v_idx].append(el)

    actions: List[Dict[str, Any]] = []

    # Build sequence
    for m in sorted(measures_map.keys()):
        for v_idx in sorted(measures_map[m].keys()):
            voice_elements = measures_map[m][v_idx]
            if not voice_elements:
                continue

            for elem_idx, elem in enumerate(voice_elements):
                abs_start_tick = (m - 1) * time_sig_ticks + elem.tick_in_measure

                if elem.is_rest:
                    params: Dict[str, Any] = {
                        "duration": elem.duration_dict,
                        "advanceCursorAfterAction": True,
                        "measure": m,
                        "startTick": abs_start_tick,
                        "voice": v_idx,
                        "staffIdx": staff_idx,
                        "staff_idx": staff_idx
                    }
                    actions.append({
                        "action": "addRest",
                        "params": params
                    })
                else:
                    # Single note or Chord
                    for pitch_idx, (midi_p, tpc_val) in enumerate(elem.pitches):
                        is_chord_add = (pitch_idx > 0)
                        params: Dict[str, Any] = {
                            "pitch": midi_p,
                            "duration": elem.duration_dict,
                            "advanceCursorAfterAction": not is_chord_add,
                            "measure": m,
                            "startTick": abs_start_tick,
                            "voice": v_idx,
                            "staffIdx": staff_idx,
                            "staff_idx": staff_idx
                        }
                        if is_chord_add:
                            params["addToChord"] = True

                        actions.append({
                            "action": "addNote",
                            "params": params
                        })

    return actions, max_measure

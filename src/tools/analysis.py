"""Analysis tools for MuseScore MCP, including harmony rules checking."""

from typing import List, Dict, Any, Optional
from ..client import MuseScoreClient
from ..utils.response_formatter import run_and_format_response

def setup_analysis_tools(mcp, client: MuseScoreClient):
    """Setup analysis tools."""

    def sgn(x: int) -> int:
        if x > 0: return 1
        if x < 0: return -1
        return 0

    def is_between(note1: dict, note2: dict, n: dict) -> bool:
        """Test if pitch of note n is between note1 and note2."""
        p1, p2, pn = note1["pitchMidi"], note2["pitchMidi"], n["pitchMidi"]
        if p1 > p2:
            return pn < p1 and pn > p2
        else:
            return pn < p2 and pn > p1

    def is_augmented_int(note1: dict, note2: dict) -> bool:
        dtpc = note2["tpc"] - note1["tpc"]
        dpitch = note2["pitchMidi"] - note1["pitchMidi"]
        
        if sgn(dtpc) != sgn(dpitch):
            return False
            
        dtpc = abs(dtpc)
        dpitch = abs(dpitch) % 12
        
        if dtpc < 6: return False
        if dtpc == 7 and dpitch == 1: return True
        if dtpc == 9 and dpitch == 3: return True
        if dtpc == 11 and dpitch == 5: return True
        if dtpc == 6 and dpitch == 6: return True
        if dtpc == 8 and dpitch == 8: return True
        if dtpc == 10 and dpitch == 10: return True
        if dtpc == 12 and dpitch == 0: return True
        
        return False

    def is_octave(note1: dict, note2: dict) -> bool:
        dtpc = abs(note2["tpc"] - note1["tpc"])
        dpitch = abs(note2["pitchMidi"] - note1["pitchMidi"])
        return dpitch == 12 and dtpc == 0

    def get_triad_info(pitches: List[int]) -> Optional[Dict[str, int]]:
        if not pitches: return None
        bass_pc = min(pitches) % 12
        pcs = sorted(list(set([p % 12 for p in pitches])))
        if len(pcs) != 3: return None
        intervals = [(pc - bass_pc) % 12 for pc in pcs]
        intervals.sort()
        if intervals == [0, 3, 7] or intervals == [0, 4, 7]:
            return {"inversion": 0, "root": bass_pc, "third": (bass_pc + intervals[1]) % 12, "fifth": (bass_pc + 7) % 12}
        elif intervals == [0, 3, 8] or intervals == [0, 4, 9]:
            root = (bass_pc + intervals[2]) % 12
            return {"inversion": 1, "root": root, "third": bass_pc, "fifth": (bass_pc + intervals[1]) % 12}
        elif intervals == [0, 5, 8] or intervals == [0, 5, 9]:
            root = (bass_pc + intervals[1]) % 12
            return {"inversion": 2, "root": root, "third": (bass_pc + intervals[2]) % 12, "fifth": bass_pc}
        return None

    @mcp.tool()
    async def check_harmony_rules(start_measure: Optional[int] = None, end_measure: Optional[int] = None, key: Optional[str] = None) -> str:
        """Analyze the current score for harmony errors based on Lovelock's rules.
        
        Checks for parallel 5ths, parallel 8ths, augmented/diminished melodic intervals,
        and unresolved jumps.
        
        Args:
            start_measure: Optional. If provided, only returns errors from this measure onwards.
            end_measure: Optional. If provided, only returns errors up to this measure.
            
        Returns:
            A Markdown formatted string detailing any found violations.
        """
        response = await client.send_command("getScore")
        if response.get("status") != "success" or "result" not in response or "analysis" not in response["result"]:
            return f"Error retrieving score: {response.get('message', 'Unknown error')}"
            
        score_data = response["result"]["analysis"]
        staves = score_data.get("staves", [])
        num_staves = len(staves)
        
        # Track data: dict of lists of notes. Key is track index (staff * 4 + voice)
        # Note structure: {"pitchMidi": x, "tpc": y, "tick": t, "measure": m}
        
        # We need a timeline of notes and rests per track.
        tracks = {}
        for staff_idx in range(num_staves):
            for voice in range(4):
                tracks[staff_idx * 4 + voice] = []

        # We will populate tracks with elements, sorted by tick
        for measure_data in score_data.get("measures", []):
            measure_num = measure_data["measure"]
            for staff_idx in range(num_staves):
                staff_key = f"staff{staff_idx}"
                elements = measure_data.get("elements", {}).get(staff_key, [])
                for el in elements:
                    if el.get("name") in ["Chord", "Rest"]:
                        voice = el.get("voice", 0)
                        track = staff_idx * 4 + voice
                        
                        if el["name"] == "Chord" and el.get("notes"):
                            # The plugin takes the top note of the chord (notes[notes.length-1] in QML)
                            # But let's take the highest pitch or the last one.
                            # In QML it was `var note = notes[notes.length-1];`
                            note = el["notes"][-1]
                            tracks[track].append({
                                "type": "note",
                                "pitchMidi": note["pitchMidi"],
                                "tpc": note["tpc"],
                                "pitchName": note.get("pitchName", ""),
                                "tick": el.get("startTick", 0),
                                "measure": measure_num
                            })
                        elif el["name"] == "Rest":
                            tracks[track].append({
                                "type": "rest",
                                "tick": el.get("startTick", 0),
                                "measure": measure_num
                            })

        errors = []
        
        # Infer tonality
        tonic_pc = None
        if key:
            key_map = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11}
            k_clean = key.lower().replace(" minor", "").replace(" major", "").replace("m", "").strip()
            if k_clean in key_map:
                tonic_pc = key_map[k_clean]
        
        if tonic_pc is None:
            # Try to get KeySig from the score elements
            key_sig_val = None
            for measure_data in score_data.get("measures", []):
                for staff_idx in range(num_staves):
                    staff_key = f"staff{staff_idx}"
                    for el in measure_data.get("elements", {}).get(staff_key, []):
                        if el.get("name") == "KeySig" and "key" in el:
                            key_sig_val = el["key"]
                            break
                    if key_sig_val is not None: break
                if key_sig_val is not None: break
                
            # Infer from last note in the lowest active track
            last_tick = -1
            for t, els in tracks.items():
                for el in els:
                    if el["type"] == "note" and el["tick"] > last_tick:
                        last_tick = el["tick"]
            
            if last_tick >= 0:
                notes_at_last_tick = []
                for t, els in tracks.items():
                    for el in els:
                        if el["type"] == "note" and el["tick"] == last_tick:
                            notes_at_last_tick.append(el["pitchMidi"])
                if notes_at_last_tick:
                    bass_pc = min(notes_at_last_tick) % 12
                    if key_sig_val is not None:
                        major_tonic = (key_sig_val * 7) % 12
                        minor_tonic = (major_tonic - 3) % 12
                        if bass_pc == major_tonic:
                            tonic_pc = major_tonic
                        elif bass_pc == minor_tonic:
                            tonic_pc = minor_tonic
                        else:
                            tonic_pc = bass_pc
                    else:
                        tonic_pc = bass_pc
        
        if tonic_pc is None:
            tonic_pc = 0
            
        sensible_pc = (tonic_pc - 1) % 12
        
        # Pass 1 & 2 preparation: create sequences of valid notes per track
        track_notes = {}
        for t, elements in tracks.items():
            # sort by tick just in case
            elements = sorted(elements, key=lambda e: e["tick"])
            notes_only = []
            for el in elements:
                if el["type"] == "note":
                    # skip repeated pitches for harmony check in Pass 1 as done by `curNote[track].pitch != note.pitch`
                    if not notes_only or notes_only[-1]["pitchMidi"] != el["pitchMidi"]:
                        notes_only.append(el)
            track_notes[t] = notes_only

        active_track_ids = [t for t, notes in track_notes.items() if len(notes) > 0]
        active_track_ids.sort()
        
        ambitus_limits = {}
        if len(active_track_ids) == 4:
            ambitus_limits = {
                active_track_ids[0]: (60, 81, "Soprano"),
                active_track_ids[1]: (53, 74, "Alto"),
                active_track_ids[2]: (48, 69, "Tenor"),
                active_track_ids[3]: (40, 64, "Bass"),
            }

        # Pass 1: Voice leading rules & Ambitus
        for t, notes in track_notes.items():
            # Check Ambitus
            if t in ambitus_limits:
                min_pitch, max_pitch, voice_name = ambitus_limits[t]
                for n in notes:
                    if n["pitchMidi"] < min_pitch or n["pitchMidi"] > max_pitch:
                        errors.append((f"- **Measure {n['measure']}** (Track {t}): Out of ambitus for {voice_name} ({n['pitchName']})", n['measure']))
            
            for i in range(1, len(notes)):
                n1 = notes[i-1]
                n2 = notes[i]
                
                # Check Augmented
                if is_augmented_int(n1, n2):
                    errors.append((f"- **Measure {n2['measure']}** (Track {t}): Augmented interval between {n1['pitchName']} and {n2['pitchName']}", n2['measure']))
                
                dtpc = n2["tpc"] - n1["tpc"]
                dpitch = n2["pitchMidi"] - n1["pitchMidi"]
                same_sgn = sgn(dtpc) == sgn(dpitch)
                
                abs_dtpc = abs(dtpc)
                abs_dpitch = abs(dpitch) % 12
                
                # Diminished 4th or 7th
                if not same_sgn:
                    if abs_dtpc == 8 and abs_dpitch == 4:
                        errors.append((f"- **Measure {n2['measure']}** (Track {t}): Diminished 4th between {n1['pitchName']} and {n2['pitchName']}", n2['measure']))
                    elif abs_dtpc == 9 and abs_dpitch == 9:
                        errors.append((f"- **Measure {n2['measure']}** (Track {t}): Diminished 7th between {n1['pitchName']} and {n2['pitchName']}", n2['measure']))
                
                # 7th and larger
                if abs(dpitch) > 9 and abs(dpitch) != 12 and abs_dtpc < 6:
                    errors.append((f"- **Measure {n2['measure']}** (Track {t}): Leap of 7th, 9th or larger", n2['measure']))

                if i >= 2:
                    n0 = notes[i-2]
                    
                    # Diminished 5th resolution
                    dtpc_01 = n1["tpc"] - n0["tpc"]
                    dpitch_01 = n1["pitchMidi"] - n0["pitchMidi"]
                    if sgn(dtpc_01) != sgn(dpitch_01):
                        if abs(dtpc_01) == 6 and (abs(dpitch_01) % 12) == 6:
                            if not is_between(n0, n1, n2):
                                errors.append((f"- **Measure {n1['measure']}** (Track {t}): Diminished 5th not followed by note within interval", n1['measure']))

                    # 6th resolution
                    same_sgn_01 = sgn(dtpc_01) == sgn(dpitch_01)
                    a_dtpc = abs(dtpc_01)
                    a_dpitch = abs(dpitch_01) % 12
                    
                    if ((a_dtpc == 11 and a_dpitch == 7 and not same_sgn_01) or
                        (a_dtpc == 4 and a_dpitch == 8 and not same_sgn_01) or
                        (a_dtpc == 3 and a_dpitch == 9 and same_sgn_01)):
                        if not is_between(n0, n1, n2):
                            errors.append((f"- **Measure {n1['measure']}** (Track {t}): 6th better avoided, must be followed by note within interval", n1['measure']))
                        else:
                            errors.append((f"- **Measure {n1['measure']}** (Track {t}): 6th better avoided", n1['measure']))

                    # Octave resolution
                    if is_octave(n1, n2) and not is_between(n1, n2, n0):
                        errors.append((f"- **Measure {n2['measure']}** (Track {t}): Octave should be preceded by note within compass", n2['measure']))
                    if is_octave(n0, n1) and not is_between(n0, n1, n2):
                        errors.append((f"- **Measure {n1['measure']}** (Track {t}): Octave should be followed by note within compass", n1['measure']))

                # Sensible resolution check
                is_outer = (t == active_track_ids[0] or t == active_track_ids[-1]) if active_track_ids else False
                if n1["pitchMidi"] % 12 == sensible_pc:
                    if n2["pitchMidi"] != n1["pitchMidi"] + 1:
                        if is_outer:
                            errors.append((f"- **Measure {n1['measure']}** (Track {t}): Sensible in outer voice not resolved to tonic ({n1['pitchName']} -> {n2['pitchName']})", n1['measure']))
                        else:
                            errors.append((f"- **Measure {n1['measure']}** (Track {t}): Sensible in inner voice not resolved to tonic ({n1['pitchName']} -> {n2['pitchName']})", n1['measure']))

        # Pass 2: Parallels (using simultaneous ticks)
        # Rebuild elements ordered by tick across all tracks to find simultaneous movements
        all_ticks = set()
        for t, els in tracks.items():
            for el in els:
                all_ticks.add(el["tick"])
                
        sorted_ticks = sorted(list(all_ticks))
        
        # State: last note played on each track
        cur_note = {t: None for t in tracks.keys()}
        prev_note = {t: None for t in tracks.keys()}
        # State: is track currently resting? (Starts as True before first note)
        cur_rest = {t: True for t in tracks.keys()}
        prev_rest = {t: True for t in tracks.keys()}
        # State: did track change pitch this tick?
        changed = {t: False for t in tracks.keys()}
        
        track_elements = {t: {el["tick"]: el for el in els} for t, els in tracks.items()}
        
        for tick in sorted_ticks:
            for t in tracks.keys():
                el = track_elements[t].get(tick)
                if el:
                    if el["type"] == "note":
                        if not cur_rest[t] and cur_note[t] and cur_note[t]["pitchMidi"] != el["pitchMidi"]:
                            prev_note[t] = cur_note[t]
                            prev_rest[t] = cur_rest[t]
                            changed[t] = True
                        elif cur_rest[t]:
                            # Was resting, now a note. We don't consider this a pitch change for parallel detection
                            # since it requires previous note
                            changed[t] = False
                        else:
                            # Same pitch, no change
                            changed[t] = False
                            
                        cur_rest[t] = False
                        cur_note[t] = el
                    elif el["type"] == "rest":
                        if not cur_rest[t]:
                            prev_note[t] = cur_note[t]
                            prev_rest[t] = cur_rest[t]
                            cur_rest[t] = True
                            changed[t] = False
                else:
                    changed[t] = False
            
            # Vertical rules (Voice Crossing and Spacing)
            note_started_this_tick = any(track_elements[t].get(tick) and track_elements[t].get(tick)["type"] == "note" for t in tracks.keys())
            if note_started_this_tick:
                active_tracks = [t for t in tracks.keys() if not cur_rest[t] and cur_note[t]]
                active_tracks.sort()
                
                # Voice crossing
                for i in range(len(active_tracks)):
                    for j in range(i+1, len(active_tracks)):
                        t1 = active_tracks[i]
                        t2 = active_tracks[j]
                        p1 = cur_note[t1]["pitchMidi"]
                        p2 = cur_note[t2]["pitchMidi"]
                        if p1 < p2:
                            m = cur_note[t1]['measure']
                            errors.append((f"- **Measure {m}** (Tracks {t1}, {t2}): Voice crossing ({cur_note[t1]['pitchName']} is below {cur_note[t2]['pitchName']})", m))

                # Spacing (Position ouverte)
                if len(active_tracks) >= 3:
                    for i in range(len(active_tracks) - 2):
                        t1 = active_tracks[i]
                        t2 = active_tracks[i+1]
                        p1 = cur_note[t1]["pitchMidi"]
                        p2 = cur_note[t2]["pitchMidi"]
                        if p1 - p2 > 12:
                            m = cur_note[t1]['measure']
                            errors.append((f"- **Measure {m}** (Tracks {t1}, {t2}): Spacing > 1 octave between upper voices ({cur_note[t1]['pitchName']} and {cur_note[t2]['pitchName']})", m))

                # Doubling rules
                active_pitches = [cur_note[t]["pitchMidi"] for t in active_tracks]
                active_pcs = [p % 12 for p in active_pitches]
                
                # 1. Sensible doubling
                if active_pcs.count(sensible_pc) >= 2:
                    m = cur_note[active_tracks[0]]['measure']
                    errors.append((f"- **Measure {m}**: Doubled leading tone (sensible)", m))
                
                # 2. Third doubling in root position
                chord_info = get_triad_info(active_pitches)
                if chord_info and chord_info["inversion"] == 0:
                    third_pc = chord_info["third"]
                    if active_pcs.count(third_pc) >= 2:
                        m = cur_note[active_tracks[0]]['measure']
                        errors.append((f"- **Measure {m}**: Doubled third in root position triad", m))
                    if chord_info["inversion"] == 2:
                        m = cur_note[active_tracks[0]]['measure']
                        errors.append((f"- **Measure {m}**: 6/4 chord (2nd inversion) is unstable, must be passing or cadential", m))

            # Check false relations
            track_indices = list(tracks.keys())
            for t1 in track_indices:
                if changed[t1] and cur_note[t1]:
                    for t2 in track_indices:
                        if t1 != t2 and prev_note[t2] and not prev_rest[t2]:
                            if (cur_note[t1]["tpc"] % 7 == prev_note[t2]["tpc"] % 7) and (cur_note[t1]["tpc"] != prev_note[t2]["tpc"]):
                                m = cur_note[t1]['measure']
                                errors.append((f"- **Measure {m}** (Tracks {t1}, {t2}): False relation ({prev_note[t2]['pitchName']} followed by {cur_note[t1]['pitchName']})", m))

            
            # Compare all pairs of tracks that changed this tick
            for i, t1 in enumerate(track_indices):
                if not changed[t1] or prev_rest[t1]:
                    continue
                dir1 = sgn(cur_note[t1]["pitchMidi"] - prev_note[t1]["pitchMidi"])
                if dir1 == 0: continue
                
                for j in range(i+1, len(track_indices)):
                    t2 = track_indices[j]
                    if changed[t2] and not prev_rest[t2]:
                        dir2 = sgn(cur_note[t2]["pitchMidi"] - prev_note[t2]["pitchMidi"])
                        if dir1 == dir2: # Parallel motion
                            cint = cur_note[t1]["pitchMidi"] - cur_note[t2]["pitchMidi"]
                            pint = prev_note[t1]["pitchMidi"] - prev_note[t2]["pitchMidi"]
                            
                            cint_mod = abs(cint) % 12
                            
                            # Determine if voices are extreme (outer) voices, and if top voice moves by step
                            active_tracks_now = [t for t in track_indices if not cur_rest[t] and cur_note[t]]
                            active_tracks_now.sort()
                            is_extreme = (len(active_tracks_now) >= 2 and t1 == active_tracks_now[0] and t2 == active_tracks_now[-1])
                            upper_voice_step = abs(cur_note[t1]["pitchMidi"] - prev_note[t1]["pitchMidi"]) <= 2

                            # Check Unison (cint == 0)
                            if cint == 0:
                                if pint == 0:
                                    errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Parallel Unison", cur_note[t1]['measure']))
                                else:
                                    errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Direct Unison", cur_note[t1]['measure']))

                            # Check 5th (mod 12 == 7)
                            if cint_mod == 7:
                                if cint == pint:
                                    errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Parallel 5th", cur_note[t1]['measure']))
                                else:
                                    if is_extreme:
                                        errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Direct 5th between extreme voices", cur_note[t1]['measure']))
                                    elif not upper_voice_step:
                                        errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Direct 5th (upper voice leaps)", cur_note[t1]['measure']))
                                    
                            # Check 8ve (mod 12 == 0 and cint != 0)
                            if cint_mod == 0 and cint != 0:
                                if cint == pint:
                                    errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Parallel 8ve", cur_note[t1]['measure']))
                                else:
                                    if is_extreme:
                                        errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Direct 8ve between extreme voices", cur_note[t1]['measure']))
                                    elif not upper_voice_step:
                                        errors.append((f"- **Measure {cur_note[t1]['measure']}** (Tracks {t1}, {t2}): Direct 8ve (upper voice leaps)", cur_note[t1]['measure']))

        # Filter errors by measure range if provided and remove exact duplicates
        filtered_errors = []
        seen_errors = set()
        for err, m_num in errors:
            if start_measure is not None and m_num < start_measure:
                continue
            if end_measure is not None and m_num > end_measure:
                continue
            if err not in seen_errors:
                filtered_errors.append(err)
                seen_errors.add(err)

        if not filtered_errors:
            msg = "✅ No harmony rules violations found"
            if start_measure or end_measure:
                msg += f" in measures {start_measure or 1} to {end_measure or 'end'}"
            return msg + "!"
            
        report = "### Harmony Rule Violations\n\n"
        report += "\n".join(filtered_errors)
        return report


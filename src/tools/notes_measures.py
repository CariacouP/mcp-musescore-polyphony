"""Notes and measures tools for MuseScore MCP."""

from typing import List, Optional
from ..client import MuseScoreClient
from ..utils.response_formatter import run_and_format_response


def setup_notes_measures_tools(mcp, client: MuseScoreClient):
    """Setup notes and measures tools."""
    
    @mcp.tool()
    async def add_note(
        pitch: int = 64, 
        duration: dict = {"numerator": 1, "denominator": 4}, 
        advance_cursor_after_action: bool = True,
        voice: Optional[int] = None,
        staff_idx: Optional[int] = None,
        measure: Optional[int] = None
    ):
        """Add a note at the current cursor position or specified staff/voice/measure with specified pitch and duration.
        
        Args:
            pitch: MIDI pitch value (0-127, where 60 is middle C)
            duration: Duration as {"numerator": int, "denominator": int} (e.g., {"numerator": 1, "denominator": 2} for half note)
            advance_cursor_after_action: Whether to move cursor to next position after adding note
            voice: Voice index (0-based: 0=Voice 1 / Soprano, 1=Voice 2 / Alto, 2=Voice 3, 3=Voice 4)
            staff_idx: Staff index (0-based: 0=Staff 1/Treble, 1=Staff 2/Bass)
            measure: Measure number (1-based, e.g., 9 for measure 9)
        """
        payload = {
            "pitch": pitch, 
            "duration": duration,
            "advanceCursorAfterAction": advance_cursor_after_action
        }
        if voice is not None:
            payload["voice"] = voice
        if staff_idx is not None:
            payload["staffIdx"] = staff_idx
            payload["staff_idx"] = staff_idx
        if measure is not None:
            payload["measure"] = measure

        return await run_and_format_response(client, "addNote", payload)

    @mcp.tool()
    async def add_rest(duration: dict = {"numerator": 1, "denominator": 4}, advance_cursor_after_action: bool = True):
        """Add a rest at the current cursor position.
        
        Args:
            duration: Duration as {"numerator": int, "denominator": int} (e.g., {"numerator": 1, "denominator": 4} for quarter rest)
            advance_cursor_after_action: Whether to move cursor to next position after adding rest
        """
        return await run_and_format_response(client, "addRest", {
            "duration": duration,
            "advanceCursorAfterAction": advance_cursor_after_action
        })

    @mcp.tool()
    async def add_tuplet(duration: dict = {"numerator": 1, "denominator": 4}, ratio: dict = {"numerator": 3, "denominator": 2}, advance_cursor_after_action: bool = True):
        """Add a tuplet at the current cursor position.
        
        Args:
            duration: Base duration as {"numerator": int, "denominator": int}
            ratio: Tuplet ratio as {"numerator": int, "denominator": int} (e.g., {"numerator": 3, "denominator": 2} for triplet)
            advance_cursor_after_action: Whether to move cursor to next position after adding tuplet
        """
        return await run_and_format_response(client, "addTuplet", {
            "duration": duration,
            "ratio": ratio,
            "advanceCursorAfterAction": advance_cursor_after_action
        })

    @mcp.tool()
    async def add_lyrics(lyrics: List[str], verse: int = 0):
        """Add lyrics to consecutive notes starting from the current cursor position.
        
        Args:
            lyrics: List of lyric syllables to add (e.g., ["Hel", "lo", "world"])
            verse: Verse number (0-based, default is 0 for first verse)
        """
        return await run_and_format_response(client, "addLyrics", {
            "lyrics": lyrics,
            "verse": verse
        })

    @mcp.tool()
    async def insert_measure():
        """Insert a measure at the current position."""
        return await run_and_format_response(client, "insertMeasure")

    @mcp.tool()
    async def append_measure(count: int = 1):
        """Append measures to the end of the score."""
        return await run_and_format_response(client, "appendMeasure", {"count": count})

    @mcp.tool()
    async def delete_selection(measure: Optional[int] = None):
        """Delete the current selection or specified measure."""
        params = {}
        if measure is not None:
            params["measure"] = measure
        return await run_and_format_response(client, "deleteSelection", params)

    @mcp.tool()
    async def clear_annotations(prefix: str = "@"):
        """Clear all StaffText and SystemText annotations that start with the specified prefix.
        
        Args:
            prefix: The text prefix that identifies annotations meant for the AI (default: "@")
        """
        return await run_and_format_response(client, "clearAnnotations", {"prefix": prefix})

    @mcp.tool()
    async def write_lilypond(
        lilypond_code: str,
        start_measure: int = 1,
        staff_idx: int = 0
    ) -> str:
        """Write LilyPond notation (notes, rests, chords, polyphony) into the MuseScore partition.
        Automatically checks score length and appends measures if needed.
        Executes in a single atomic batch sequence with strict voice ordering (Voice 1 then Voice 2 etc.)
        for maximum reliability, speed, and single-step undo.

        Args:
            lilypond_code: LilyPond music snippet (e.g. "c'4 d' e' f' | g'2 c''" or "<< { c''2 d'' } \\\\ { e'2 f' } >>")
            start_measure: Measure number to start writing into (1-based, default: 1)
            staff_idx: Staff index (0-based: 0=Staff 1/Treble, 1=Staff 2/Bass)
        """
        try:
            from ..utils.lilypond_writer import lilypond_to_actions
            actions, max_measure = lilypond_to_actions(lilypond_code, start_measure=start_measure, staff_idx=staff_idx)
            
            if not actions:
                return "No playable music elements found in provided LilyPond code."

            # Check if we need to auto-append measures
            score_res = await client.send_command("getScore")
            num_measures = 0
            if isinstance(score_res, dict):
                res_payload = score_res.get("result", score_res)
                if isinstance(res_payload, dict):
                    analysis = res_payload.get("analysis", {})
                    num_measures = analysis.get("numMeasures", 0)

            if num_measures > 0 and max_measure > num_measures:
                needed = max_measure - num_measures
                await client.send_command("appendMeasure", {"count": needed})

            # Process the action sequence
            res = await client.send_command("processSequence", {"sequence": actions})
            
            if isinstance(res, dict) and (res.get("status") == "success" or res.get("success") is True):
                return f"[Message] Successfully written LilyPond snippet into measure(s) {start_measure} to {max_measure} (Staff {staff_idx}, {len(actions)} actions)."
            else:
                err = res.get("error", "Unknown error") if isinstance(res, dict) else str(res)
                return f"Error executing LilyPond sequence: {err}"
        except Exception as e:
            return f"Error processing LilyPond code: {e}"

    @mcp.tool()
    async def undo():
        """Undo the last action."""
        return await run_and_format_response(client, "undo")
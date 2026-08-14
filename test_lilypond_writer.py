import unittest
import asyncio
from src.utils.lilypond_writer import (
    parse_lilypond_pitch,
    parse_lilypond_duration,
    split_lilypond_voices,
    lilypond_to_actions
)

class TestLilyPondWriter(unittest.TestCase):

    def test_pitch_parsing(self):
        # c' is Middle C = 60
        midi, tpc = parse_lilypond_pitch("c'")
        self.assertEqual(midi, 60)
        self.assertEqual(tpc, 14)

        # c is C3 = 48
        midi, tpc = parse_lilypond_pitch("c")
        self.assertEqual(midi, 48)

        # c'' is C5 = 72
        midi, tpc = parse_lilypond_pitch("c''")
        self.assertEqual(midi, 72)

        # c, is C2 = 36
        midi, tpc = parse_lilypond_pitch("c,")
        self.assertEqual(midi, 36)

        # fis' is F#4 = 66
        midi, tpc = parse_lilypond_pitch("fis'")
        self.assertEqual(midi, 66)
        self.assertEqual(tpc, 20)

        # bes' is Bb4 = 70
        midi, tpc = parse_lilypond_pitch("bes'")
        self.assertEqual(midi, 70)
        self.assertEqual(tpc, 12)

    def test_duration_parsing(self):
        dur, ticks = parse_lilypond_duration("4")
        self.assertEqual(dur, {"numerator": 1, "denominator": 4})
        self.assertEqual(ticks, 480)

        dur, ticks = parse_lilypond_duration("2.")
        self.assertEqual(dur, {"numerator": 3, "denominator": 4})
        self.assertEqual(ticks, 1440)

        dur, ticks = parse_lilypond_duration("8")
        self.assertEqual(dur, {"numerator": 1, "denominator": 8})
        self.assertEqual(ticks, 240)

        dur, ticks = parse_lilypond_duration("1")
        self.assertEqual(dur, {"numerator": 1, "denominator": 1})
        self.assertEqual(ticks, 1920)

    def test_split_voices(self):
        code_double_slash = "<< { c''4 d'' e'' f'' } \\\\ { e'4 f' g' a' } >>"
        voices = split_lilypond_voices(code_double_slash)
        self.assertEqual(len(voices), 2)
        self.assertEqual(voices[0], "c''4 d'' e'' f''")
        self.assertEqual(voices[1], "e'4 f' g' a'")

        code_new_voice = '<< \\new Voice = "1" { c\'\'2 d\'\' } \\new Voice = "2" { e\'1 } >>'
        voices = split_lilypond_voices(code_new_voice)
        self.assertEqual(len(voices), 2)
        self.assertEqual(voices[0], "c''2 d''")
        self.assertEqual(voices[1], "e'1")

    def test_lilypond_to_actions_monophonic(self):
        code = "c'4 d' e' f' | g'2 c''"
        actions, max_measure = lilypond_to_actions(code, start_measure=1, staff_idx=0)
        self.assertEqual(max_measure, 2)
        self.assertEqual(len(actions), 6)

        # First note in measure 1 has explicit coordinates
        self.assertEqual(actions[0]["action"], "addNote")
        self.assertEqual(actions[0]["params"]["pitch"], 60)
        self.assertEqual(actions[0]["params"]["measure"], 1)
        self.assertEqual(actions[0]["params"]["voice"], 0)

        # First note in measure 2 has explicit coordinates for measure 2
        self.assertEqual(actions[4]["action"], "addNote")
        self.assertEqual(actions[4]["params"]["pitch"], 67)
        self.assertEqual(actions[4]["params"]["measure"], 2)
        self.assertEqual(actions[4]["params"]["voice"], 0)

    def test_lilypond_to_actions_polyphonic_ordering(self):
        code = "<< { c''4 d'' e'' f'' | g''1 } \\\\ { e'4 f' g' a' | c'1 } >>"
        actions, max_measure = lilypond_to_actions(code, start_measure=3, staff_idx=0)
        self.assertEqual(max_measure, 4)

        # Measure 3 Voice 0: 4 notes
        # Measure 3 Voice 1: 4 notes
        # Measure 4 Voice 0: 1 note
        # Measure 4 Voice 1: 1 note
        self.assertEqual(len(actions), 10)

        # Check that Measure 3 Voice 0 comes before Measure 3 Voice 1
        m3_v0_first = actions[0]["params"]
        self.assertEqual(m3_v0_first["measure"], 3)
        self.assertEqual(m3_v0_first["voice"], 0)

        m3_v1_first = actions[4]["params"]
        self.assertEqual(m3_v1_first["measure"], 3)
        self.assertEqual(m3_v1_first["voice"], 1)

        # Check Measure 4 Voice 0 then Voice 1
        m4_v0_first = actions[8]["params"]
        self.assertEqual(m4_v0_first["measure"], 4)
        self.assertEqual(m4_v0_first["voice"], 0)

        m4_v1_first = actions[9]["params"]
        self.assertEqual(m4_v1_first["measure"], 4)
        self.assertEqual(m4_v1_first["voice"], 1)

    def test_rests_and_chords(self):
        code = "r4 <c' e' g'>4 r2"
        actions, max_measure = lilypond_to_actions(code, start_measure=1, staff_idx=0)
        self.assertEqual(max_measure, 1)
        # 1 rest + 3 chord notes + 1 rest = 5 actions
        self.assertEqual(len(actions), 5)
        self.assertEqual(actions[0]["action"], "addRest")
        self.assertEqual(actions[1]["action"], "addNote")
        self.assertEqual(actions[2]["action"], "addNote")
        self.assertTrue(actions[2]["params"].get("addToChord", False))
        self.assertEqual(actions[3]["action"], "addNote")
        self.assertTrue(actions[3]["params"].get("addToChord", False))
        self.assertEqual(actions[4]["action"], "addRest")


async def run_integration_test():
    import sys
    from src.client import MuseScoreClient
    from src.tools.notes_measures import setup_notes_measures_tools

    class MockMCP:
        def __init__(self):
            self.tools = {}
        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

    print("=== Test d'intégration WebSocket avec MuseScore ===")
    client = MuseScoreClient()
    mcp = MockMCP()
    setup_notes_measures_tools(mcp, client)

    test_polyphony = "<< { c''4 d'' e'' f'' | g''2 c''' } \\\\ { e'4 f' g' a' | e'2 e' } >>"
    print(f"Code LilyPond à injecter :\n{test_polyphony}\n")
    
    print("1. Écriture polyphonique (Mesures 1 à 2) :")
    write_tool = mcp.tools["write_lilypond"]
    result1 = await write_tool(lilypond_code=test_polyphony, start_measure=1, staff_idx=0)
    print(result1)

    print("\n2. Test Auto-Append (Écriture au-delà des mesures existantes, ex: Mesure 7 à 8) :")
    append_polyphony = "<< { g''2 a'' | b''1 } \\\\ { c''2 f' | g'1 } >>"
    result2 = await write_tool(lilypond_code=append_polyphony, start_measure=7, staff_idx=0)
    print(result2)


if __name__ == "__main__":
    import sys
    if "--integration" in sys.argv:
        asyncio.run(run_integration_test())
    else:
        unittest.main()


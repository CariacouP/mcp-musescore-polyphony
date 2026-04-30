import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ResponseFormatter")

async def run_and_format_response(client, action: str, params: Optional[Dict[str, Any]] = None):
    """
    Executes a command and formats the response to save LLM tokens.
    Converts raw JSON selections and scores into concise LilyPond strings.
    """
    res = await client.send_command(action, params)

    if not isinstance(res, dict):
        return res

    if res.get("success"):
        output = []

        # Include any text message from the server
        if "message" in res and res["message"]:
            # If message is a dictionary, ignore or serialize it differently, but usually it's a string
            if isinstance(res["message"], str):
                output.append(f"[Message] {res['message']}")
            else:
                output.append(f"[Message] Action successful")

        # Format currentSelection if present
        if "currentSelection" in res:
            from .lilypond_converter import json_to_lilypond
            sel = res["currentSelection"]
            lily_str = json_to_lilypond(sel)

            meta = []
            score_info = res.get("currentScore", {})
            if not isinstance(score_info, dict):
                score_info = {}

            if "startTick" in sel:
                tick = sel["startTick"]
                # Default math fallback
                measure_num = (tick // 1920) + 1
                beat_num = ((tick % 1920) // 480) + 1

                if "measures" in score_info:
                    measures = score_info["measures"]
                    # Sort and find
                    measures = sorted(measures, key=lambda m: m.get("startTick", 0))
                    current_m = measures[0] if measures else {}
                    for m in measures:
                        if m.get("startTick", 0) > tick:
                            break
                        current_m = m
                    measure_num = current_m.get("measure", measure_num)
                    m_start = current_m.get("startTick", 0)
                    beat_num = (max(0, tick - m_start) // 480) + 1

                meta.append(f"Mesure: {measure_num}")
                meta.append(f"Temps: {beat_num}")

            if "startStaff" in sel:
                start_s = sel["startStaff"]
                end_s = sel.get("endStaff", start_s)
                staff_name = f"{start_s}-{end_s}" if start_s != end_s else str(start_s)

                if "staves" in score_info:
                    staves = score_info["staves"]
                    if 0 <= start_s < len(staves):
                        st_info = staves[start_s]
                        name = st_info.get("shortName") or st_info.get("name")
                        if name:
                            staff_name = name

                meta.append(f"Portée: {staff_name}")

            if "numMeasures" in score_info:
                meta.append(f"Total Mesures: {score_info['numMeasures']}")

            meta_str = ", ".join(meta) if meta else "Aucune métadonnée"
            output.append(f"[Métadonnées] {meta_str}\n[Partition]\n{lily_str}")

        elif "analysis" in res:
            from .lilypond_converter import json_to_lilypond
            analysis = res["analysis"]
            lily_str = json_to_lilypond(analysis)

            meta = []
            if "numMeasures" in analysis:
                meta.append(f"Total Mesures: {analysis['numMeasures']}")

            num_staves = len(analysis.get("staves", []))
            if num_staves > 0:
                meta.append(f"Nombre de portées: {num_staves}")

            meta_str = ", ".join(meta) if meta else "Aucune métadonnée"
            output.append(f"[Métadonnées] {meta_str}\n[Partition]\n{lily_str}")

        if output:
            return "\n\n".join(output)

    return res

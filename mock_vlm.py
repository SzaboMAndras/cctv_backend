def ask_required_information(prompt):
    # Megvizsgálja, hogy az adott prompt eldöntéséhez milyen kontextus kell
    
    p_lower = prompt.lower()
    
    if "füst" in p_lower or "smoke" in p_lower:
        return {
            "need_type": "frame",
            "max_time_window_seconds": 0,
            "reasoning": "A füst jelenléte egyetlen frame alapján eldönthető."
        }
    elif "szalad" in p_lower or "mozgás" in p_lower:
        return {
            "need_type": "video",
            "max_time_window_seconds": 10,
            "reasoning": "A mozgás/szaladás igazolásához az aktuális esemény 10 másodperces videója szükséges."
        }
    elif "bámészkodik" in p_lower or "hosszan" in p_lower or "csomagot hagy" in p_lower:
        return {
            "need_type": "multi_video",
            "max_time_window_seconds": 60, # Pl. az elmúlt 30 másodperc eseményei
            "reasoning": "Hosszabb folyamat vizsgálatához az elmúlt 60 másodperc eseményeinek videóira van szükség."
        }
    elif "kovács géza" in p_lower:
        return {
            "need_type": "insufficient_info",
            "max_time_window_seconds": 0,
            "reasoning": "Ehhez nincs elég információ a kamerarendszerből."
        }
    else:
        # Alapértelmezett: egy videó kérése
        return {
            "need_type": "video",
            "max_time_window_seconds": 10,
            "reasoning": "Alapértelmezett eseményvizsgálat egyedi videó alapján."
        }

def analyze_with_vlm(prompt, context_events, requirement):
    # Prompt és kontextus kiértékelése

    triggered = False
    description = "A feltétel nem teljesült."

    for ev in context_events:
        if "füst" in prompt.lower() and ev.get('event_type') == 'smoke':
            triggered = True
            description = "Füst érzékelve."
            break
        elif "szalad" in prompt.lower()  and ev.get('event_type') == 'movement':
            triggered = True
            description = "Szaladó ember érzékelve."
            break
        elif "bámészkodik" in prompt.lower()  and ev.get('event_type') == 'person' and len(context_events) >= 3:
                    triggered = True
                    description = "Bámészkodó ember érzékelve."
                    break

    return {
        "triggered": triggered,
        "description": description
    }
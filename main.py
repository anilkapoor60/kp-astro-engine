def build_kp_249_table() -> List[Dict]:
    """Generates the exact 249 KP Horary Sub Table with precise boundary handling."""
    table = []
    curr_lon = 0.0

    for nak_idx, (nak_name, star_lord) in enumerate(NAKSHATRAS):
        start_lord_idx = DASHA_LORDS.index(star_lord)
        for i in range(9):
            sub_lord = DASHA_LORDS[(start_lord_idx + i) % 9]
            sub_span_deg = ((DASHA_YEARS[(start_lord_idx + i) % 9] / TOTAL_YEARS) * NAKSHATRA_SPAN) / 60.0
            end_lon = curr_lon + sub_span_deg

            # Determine if a 30-degree boundary lies strictly BETWEEN curr_lon and end_lon
            curr_sign = int(curr_lon // 30.0)
            next_boundary = (curr_sign + 1) * 30.0

            # Only split if the boundary is genuinely crossed (avoiding float epsilon traps)
            if curr_lon < (next_boundary - 1e-5) and end_lon > (next_boundary + 1e-5) and next_boundary < 360.0:
                # Part 1: up to the boundary
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": next_boundary,
                    "sign": ZODIAC_SIGNS[curr_sign][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
                # Part 2: from boundary into next sign
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": next_boundary,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[curr_sign + 1][0],
                    "sign_lord": ZODIAC_SIGNS[curr_sign + 1][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            else:
                sign_idx = int(round(curr_lon, 4) // 30.0) % 12
                table.append({
                    "seed": len(table) + 1,
                    "start_lon": curr_lon,
                    "end_lon": end_lon,
                    "sign": ZODIAC_SIGNS[sign_idx][0],
                    "sign_lord": ZODIAC_SIGNS[sign_idx][1],
                    "star_lord": star_lord,
                    "sub_lord": sub_lord
                })
            curr_lon = end_lon

    return table

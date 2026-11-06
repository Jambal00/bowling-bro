"""Turn one week's league sheet (the text of Gary's BLS-2013 PDF) into the week's data for bb_league_weeks.

Usage:  python3 tools/league_week.py SHEET.txt PREV_WEEK.json OUT.json
  SHEET.txt      the sheet's text, as the Outlook connector returns the attached PDF (pages flattened is fine)
  PREV_WEEK.json the previous week's `data` from bb_league_weeks (needed for handicaps, points and pins carry-over)
  OUT.json       written only when every check passes

Prints a short report. Exit code 0 = all checks passed, 1 = problems (nothing written), 2 = bad input.
No third-party packages; contains no league data itself.

What it checks before it will write anything:
  - every bowler's series = game 1 + game 2 + game 3
  - every bowler's season pins = last week's season pins + this week's series
  - every team's handicap games on the results table = its bowlers' games + the handicaps they carried in
    (last week's sheet; a first night uses that night's sheet), counting blinds ("a110" lines); a bowler who
    subbed for another team is found from the mismatch and moved to that team for the week (team, rosterTeam, subFor)
  - every match's individual points are reproduced by exactly one pairing of bowlers (ties prefer roster order)
"""
import json, re, sys, itertools

def num(s):
    s = s.replace(" ½", ".5").replace("½", ".5").strip()
    return float(s)

K = lambda s: re.sub("[^A-Z0-9]", "", s.upper())

def short_key(n):
    return K(" ".join(x for x in n.replace(".", "").split() if len(x) > 1))

def parse(T):
    T = re.sub(r"\s+", " ", T)
    m = re.search(r"(\d+)/(\d+)/(\d{4}) Week (\d+) of (\d+)", T)
    if not m: raise ValueError("no 'Week N of M' header")
    wk, weeks_in = int(m.group(4)), int(m.group(5))
    date = "%s-%02d-%02d" % (m.group(3), int(m.group(1)), int(m.group(2)))
    lane = ["1-2", "3-4", "5-6", "7-8"]
    def pairs(a, b):
        seg = T.split(a, 1)[1].split(b, 1)[0]
        p = re.findall(r"(\d)- ?(\d)", seg)[:4]
        return [dict(lanes=lane[i], teams=[int(x), int(y)]) for i, (x, y) in enumerate(p)]
    sched = {str(wk + 1): pairs("Today", "Next Week"), str(wk + 2): pairs("Next Week", "Top 8")}
    ro = T.split("Team Rosters", 1)[1]
    teams = {}
    for a, b in re.findall(r"(\d) - ([A-Z0-9' ]+?) Lane \d", ro): teams[a] = b.strip()
    st = T.split("Place # Team Name", 1)[1].split("Review of", 1)[0] if "Place # Team Name" in T else T.split("HDCP 1 ", 1)[1].split("Review of", 1)[0]
    st = re.sub(r"^.*?HDCP (?=1 )", "", st)
    standings = []
    for g in re.finditer(r"(\d) (\d) ([A-Z0-9' ]+?) ([\d.]+) (\d+(?: ½)?) (\d+(?: ½)?) [\d.]+ \d+(?: ½)? \d+(?: ½)? (\d+) (\d+) (\d+)", st):
        standings.append(dict(place=int(g[1]), team=int(g[2]), pctWon=float(g[4]), won=num(g[5]), lost=num(g[6]), scratchPins=int(g[8]), hdcpPins=int(g[9])))
    rs = T.split("Review of Last Week", 1)[1].split("Season High", 1)[0]
    results = []
    for g in re.finditer(r"(\d-\d) ([A-Z0-9' ]+?) (\d+) (\d+) (\d+) (\d+) (\d+(?: ½)?) <---> ([A-Z0-9' ]+?) (\d+) (\d+) (\d+) (\d+) (\d+(?: ½)?)", rs):
        results.append(dict(lanes=g[1], a=dict(name=g[2].strip(), hdcpGames=[int(g[3]), int(g[4]), int(g[5])], hdcpTotal=int(g[6]), won=num(g[7])),
                            b=dict(name=g[8].strip(), hdcpGames=[int(g[9]), int(g[10]), int(g[11])], hdcpTotal=int(g[12]), won=num(g[13]))))
    seg = T.split("High Individual Match Points", 1)[1].split("Last Week's Top", 1)[0] if "High Individual Match Points" in T else ""
    mps = [(float(v), n) for v, n in re.findall(r"(\d+(?:\.5)?) ([A-Z][A-Z.' ]*?[A-Z])(?= \d| ?$)", seg.strip())]
    bowlers = []
    sections = re.split(r"(?=\b\d - [A-Z0-9' ]+? Lane \d)", ro)[1:]
    for sec in sections:
        team = int(sec[0])
        body = re.split(r"Total Total", sec, maxsplit=1)[1]
        body = body.split("BLS-2013", 1)[0]
        for g in re.finditer(r"(\d+) (?:[RL] )?([A-Z][A-Z.' ]*?[A-Z.]) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)(?: (a?\d+) (a?\d+) (a?\d+) (\d+) (\d+)| 0 0)?(?= \d| ?$)", body.strip()):
            b = dict(id=int(g[1]), name=g[2].strip(), avg=int(g[3]), hdcp=int(g[4]), pins=int(g[5]), games=int(g[6]), team=team)
            if g[9]:
                if g[9].startswith("a"): b["_blind"] = [int(g[9][1:]), int(g[10][1:]), int(g[11][1:])]
                else:
                    b["scores"] = [int(g[9]), int(g[10]), int(g[11])]
                    b["_series"] = int(g[12])
            bowlers.append(b)
    return dict(week=wk, weeksInSeason=weeks_in, date=date, teams=teams, standings=standings, results=results, schedule=sched, bowlers=bowlers), mps

def main(sheet_path, prev_path, out_path):
    T = open(sheet_path).read()
    prevw = json.load(open(prev_path))
    w, mps = parse(T)
    problems, notes = [], []
    if prevw.get("week") != w["week"] - 1: problems.append("previous week is %s, expected %s" % (prevw.get("week"), w["week"] - 1))
    if len(w["teams"]) != 8 or len(w["standings"]) != 8 or len(w["results"]) != 4: problems.append("sheet layout: %d teams, %d standings rows, %d results (expected 8, 8, 4)" % (len(w["teams"]), len(w["standings"]), len(w["results"])))
    if len(w["bowlers"]) < 30: problems.append("only %d bowlers read from the rosters" % len(w["bowlers"]))
    prev = {b["id"]: b for b in prevw["bowlers"]}
    ids = [b["id"] for b in w["bowlers"]]
    if len(ids) != len(set(ids)): problems.append("a bowler id appears twice")
    # 1. series and pins
    for b in w["bowlers"]:
        s = b.get("scores")
        if s and sum(s) != b["_series"]:
            g3, tot = b["_series"], s[2]            # pdftotext-style swap of game 3 and the total
            if s[0] + s[1] + g3 == tot: b["scores"] = [s[0], s[1], g3]; s = b["scores"]
            else: problems.append("%s: games %s don't add to %s" % (b["name"], s, b["_series"]))
        p = prev.get(b["id"])
        add = sum(s) if s else 0
        if p is not None and b["pins"] != p["pins"] + add: problems.append("%s: season pins %d, expected %d + %d" % (b["name"], b["pins"], p["pins"], add))
        if p is None and b["pins"] != add and add: problems.append("%s: new bowler with pins %d but series %d" % (b["name"], b["pins"], add))
    def hc_in(b):
        p = prev.get(b["id"])
        return p["hdcp"] if p and p["games"] else b["hdcp"]
    tnum = lambda name: next((int(n) for n, v in w["teams"].items() if K(v).startswith(K(name)) or K(name).startswith(K(v))), None)
    def team_games(t):
        out = [0, 0, 0]
        for b in w["bowlers"]:
            if b["team"] != t: continue
            g = b.get("scores") or b.get("_blind")
            if g:
                h = hc_in(b)
                for i in range(3): out[i] += g[i] + h
        return out
    # 2. team handicap games, finding subs from the mismatch
    sheet_games = {}
    for r in w["results"]:
        for side in "ab":
            t = tnum(r[side]["name"])
            if t is None: problems.append("results team '%s' not on the rosters" % r[side]["name"]); continue
            sheet_games[t] = r[side]["hdcpGames"]
    def diffs():
        return {t: [sheet_games[t][i] - team_games(t)[i] for i in range(3)] for t in sheet_games}
    d = diffs()
    for t_short, dv in list(d.items()):
        if any(dv) and all(x > 0 for x in dv):
            for t_long, dv2 in d.items():
                if t_long == t_short: continue
                for b in w["bowlers"]:
                    if b["team"] == t_long and b.get("scores") and [x + hc_in(b) for x in b["scores"]] == dv and [-x for x in dv2] == dv:
                        b["rosterTeam"], b["subFor"], b["team"] = t_long, t_short, t_short
                        notes.append("%s (%s) bowled for %s this week" % (b["name"], w["teams"][str(t_long)], w["teams"][str(t_short)]))
            d = diffs()
    for t, dv in diffs().items():
        if any(dv): problems.append("%s: handicap games %s don't match the results table %s" % (w["teams"][str(t)], team_games(t), sheet_games[t]))
    # 3. individual points -> games won
    listed = {}
    for b in w["bowlers"]:
        hit = [v for v, n in mps if short_key(b["name"]).startswith(K(n)) or K(n).startswith(short_key(b["name"]))]
        if hit: listed[b["id"]] = hit[0]
    for b in w["bowlers"]:
        p = prev.get(b["id"])
        b["mp"] = listed.get(b["id"], p.get("mp", 0.0) if p else 0.0)
    order = {b["id"]: i for i, b in enumerate(w["bowlers"])}
    out = {}
    for r in w["results"]:
        A, B = tnum(r["a"]["name"]), tnum(r["b"]["name"])
        def men(t):
            o = []
            for b in w["bowlers"]:
                if b["team"] != t or not (b.get("scores") or b.get("_blind")): continue
                p = prev.get(b["id"])
                known = (not b.get("_blind")) and b["id"] in listed and p is not None and (p.get("mp", 0) > 0 or p["games"] == 0)
                o.append(dict(b=b, hc=hc_in(b), pts=(b["mp"] - p.get("mp", 0)) if known else None))
            return sorted(o, key=lambda m: order[m["b"]["id"]])
        ma, mb = men(A), men(B)
        if len(ma) != len(mb): problems.append("%s v %s: %d against %d bowlers" % (r["a"]["name"], r["b"]["name"], len(ma), len(mb))); continue
        sols = []
        for perm in itertools.permutations(range(len(mb))):
            res, ok = [], True
            for i, j in enumerate(perm):
                x, y = ma[i], mb[j]
                ga = [s + x["hc"] for s in (x["b"].get("scores") or x["b"]["_blind"])]
                gb = [s + y["hc"] for s in (y["b"].get("scores") or y["b"]["_blind"])]
                pa = sum(1 if a > c else .5 if a == c else 0 for a, c in zip(ga + [sum(ga)], gb + [sum(gb)]))
                if (x["pts"] is not None and abs(pa - x["pts"]) > .01) or (y["pts"] is not None and abs(4 - pa - y["pts"]) > .01): ok = False; break
                res.append((x["b"]["id"], y["b"]["id"], [a > c for a, c in zip(ga, gb)], [c > a for a, c in zip(ga, gb)], sum(ga) > sum(gb), sum(gb) > sum(ga), pa))
            if ok: sols.append(res)
        if len(sols) > 1:
            posn = sorted((ma[i]["b"]["id"], mb[i]["b"]["id"]) for i in range(len(ma)))
            pick = [s for s in sols if sorted((a, b) for a, b, *_ in s) == posn]
            if pick: notes.append("%s v %s: %d pairings fit the points; used roster order" % (r["a"]["name"], r["b"]["name"], len(sols)))
            sols = pick
        if len(sols) != 1: problems.append("%s v %s: %s pairing of bowlers fits the points" % (r["a"]["name"], r["b"]["name"], "no" if not sols else "more than one")); continue
        for ia, ib, wa, wb, sa, sb, pa in sols[0]:
            out[ia] = dict(won=wa, wonSeries=sa, pts=pa, opp=ib); out[ib] = dict(won=wb, wonSeries=sb, pts=4 - pa, opp=ia)
    for b in w["bowlers"]:
        b.pop("_blind", None); b.pop("_series", None)
        if b["id"] in out:
            o = out[b["id"]]; b["opp"] = o["opp"]; b["won"] = o["won"]; b["wonSeries"] = o["wonSeries"]
            b["pts"] = int(o["pts"]) if o["pts"] == int(o["pts"]) else o["pts"]
    w["leagueName"] = prevw.get("leagueName", "Thursday Men's Early"); w["season"] = prevw.get("season", "2026-27"); w["center"] = prevw.get("center", "Big Al's")
    print("Week %d (%s): %d bowlers, %d bowled" % (w["week"], w["date"], len(w["bowlers"]), sum(1 for b in w["bowlers"] if b.get("scores"))))
    for n in notes: print("note:", n)
    if problems:
        print("PROBLEMS (nothing written):")
        for p in problems: print(" -", p)
        return 1
    json.dump(w, open(out_path, "w"), separators=(",", ":"))
    print("all checks passed; wrote", out_path)
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 4: print(__doc__); sys.exit(2)
    try: sys.exit(main(*sys.argv[1:]))
    except (ValueError, IndexError, KeyError) as e: print("could not read the sheet:", e); sys.exit(2)

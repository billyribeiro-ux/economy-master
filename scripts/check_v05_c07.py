"""Independent exact payoff/deviation checks for v05-c07.

No external packages, network, chapter implementation or generated writes.
Finite tree checks enumerate complete plans and every unilateral deviation in
every subgame. Probability grids supplement, rather than prove, the analytic
descriptions of continuous equilibrium sets in the manuscript.
"""

from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import product
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "content/chapters/v05-c07.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def unit(size, index):
    return tuple(F(int(j == index)) for j in range(size))


def profile_payoff(game, row, col):
    """Read the matrix directly and average independent joint outcomes."""
    require(len(row) == len(game) and len(col) == len(game[0]), "dimensions")
    require(sum(row) == sum(col) == 1, "probabilities must sum to one")
    require(all(p >= 0 for p in row + col), "negative probability")
    return tuple(sum(row[i] * col[j] * game[i][j][k]
                     for i in range(len(row)) for j in range(len(col)))
                 for k in (0, 1))


def pure_deviation_gains(game, row, col):
    current = profile_payoff(game, row, col)
    return (
        tuple(profile_payoff(game, unit(len(row), i), col)[0] - current[0]
              for i in range(len(row))),
        tuple(profile_payoff(game, row, unit(len(col), j))[1] - current[1]
              for j in range(len(col))),
    )


def is_nash(game, row, col):
    return all(g <= 0 for gains in pure_deviation_gains(game, row, col)
               for g in gains)


def pure_nash(game):
    return {(i, j) for i in range(len(game)) for j in range(len(game[0]))
            if is_nash(game, unit(len(game), i), unit(len(game[0]), j))}


def dominates(game, player, better, worse, rivals, strict):
    if player == 0:
        gains = [game[better][j][0] - game[worse][j][0] for j in rivals]
    else:
        gains = [game[i][better][1] - game[i][worse][1] for i in rivals]
    return all(g > 0 for g in gains) if strict else (
        all(g >= 0 for g in gains) and any(g > 0 for g in gains))


def plans(nodes, player):
    owned = [(name, tuple(actions)) for name, (who, actions) in nodes.items()
             if who == player]
    return [dict(zip((name for name, _ in owned), choices))
            for choices in product(*(actions for _, actions in owned))]


def tree_payoff(nodes, terminals, profile, start="root"):
    history = start
    visited = set()
    while history in nodes:
        require(history not in visited, "cycle in finite tree")
        visited.add(history)
        player, children = nodes[history]
        history = children[profile[player][history]]
    return terminals[history]


def plan_key(profile):
    return tuple(tuple(sorted(plan.items())) for plan in profile)


def tree_equilibria(nodes, terminals, every_subgame):
    """Enumerate all pure complete plans; directly test all deviations.

    Each node in these declared trees is a singleton information set, so every
    decision node begins a proper subgame or the whole game. No backward-
    induction recurrence or hand-coded maximizing action is used by this oracle.
    """
    strategy_sets = [plans(nodes, player) for player in (0, 1)]
    roots = tuple(nodes) if every_subgame else ("root",)
    answers = set()
    for profile in product(*strategy_sets):
        valid = True
        for start in roots:
            current = tree_payoff(nodes, terminals, profile, start)
            for player in (0, 1):
                for alternative in strategy_sets[player]:
                    deviated = list(profile)
                    deviated[player] = alternative
                    if tree_payoff(nodes, terminals, deviated, start)[player] > current[player]:
                        valid = False
                        break
                if not valid:
                    break
            if not valid:
                break
        if valid:
            answers.add(plan_key(profile))
    return answers


def commitment_tree(cost, reversible=False):
    nodes = {
        "root": (1, {"No": "E_No", "Lock": "E_Lock"}),
        "E_No": (0, {"Out": "No_Out", "Enter": "I_No"}),
        "I_No": (1, {"A": "No_A", "F": "No_F"}),
        "E_Lock": (0, {"Out": "Lock_Out", "Enter": "Lock_F"}),
    }
    terminals = {
        "No_Out": (0, 8), "No_A": (3, 4), "No_F": (-2, -1),
        "Lock_Out": (0, 8-cost), "Lock_F": (-2, -1-cost),
    }
    if reversible:
        nodes["E_Lock"][1]["Enter"] = "I_Lock"
        nodes["I_Lock"] = (1, {"A": "Lock_A", "F": "Lock_F"})
        terminals["Lock_A"] = (3, 4-cost)
    return nodes, terminals


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = 0
        self.exercises = 0
        self.solutions = 0
        self.in_exercises = False
        self.in_solutions = False
        self.links = []
        self.sources = set()
        self.forbidden = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h1", "html", "body", "script"}:
            self.forbidden.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.in_exercises = True
        if tag == "details" and attrs.get("class") == "solutions":
            self.in_solutions = True
        if tag == "li" and self.in_exercises:
            self.exercises += 1
        if tag == "li" and self.in_solutions:
            self.solutions += 1
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol":
            self.in_exercises = False
        if tag == "details":
            self.in_solutions = False


def check():
    checks = []
    expansion = (((7, 7), (2, 9)), ((9, 2), (4, 4)))
    require(pure_nash(expansion) == {(1, 1)}, "expansion pure NE")
    for player in (0, 1):
        require(dominates(expansion, player, 1, 0, (0, 1), True), "strict expansion dominance")
    require([sum(expansion[i][j]) for i in range(2) for j in range(2)] == [14, 11, 11, 8], "profit sums")
    transformed = tuple(tuple(tuple(3*u-5 for u in cell) for cell in row) for row in expansion)
    require(transformed[0][0] == (16, 16) and transformed[1][1] == (7, 7), "affine diagonal payoffs")
    for a, b in product(range(11), repeat=2):
        row, col = (F(a, 10), F(10-a, 10)), (F(b, 10), F(10-b, 10))
        require(is_nash(expansion, row, col) == (a == b == 0), "no extra sampled expansion NE")
        before = pure_deviation_gains(expansion, row, col)
        after = pure_deviation_gains(transformed, row, col)
        require(after == tuple(tuple(3*x for x in gains) for gains in before), "affine invariance")
    checks.append("Expansion: exact best responses, unique pure NE, 121 mixed-profile deviation audits, profit sums and affine invariance")

    weak = (((2, 2), (2, 0)), ((2, 2), (0, 2)))
    require(pure_nash(weak) == {(0, 0), (1, 0)}, "weak table pure NE")
    require(dominates(weak, 0, 0, 1, (0, 1), False), "U weakly dominates D")
    require(dominates(weak, 1, 0, 1, (0, 1), False), "L weakly dominates R")
    require(not dominates(weak, 0, 0, 1, (0, 1), True), "row not strictly dominated")
    require(dominates(weak, 1, 0, 1, (0,), True), "delete D then strict column dominance")
    require(not dominates(weak, 0, 0, 1, (0,), False), "delete R: equal row choices retained")
    require(not dominates(weak, 0, 1, 0, (0,), False), "equal choices do not weakly dominate")
    checks.append("Weak deletion: both original NE, removal of (D,L), and distinct surviving sets for the two deletion orders")

    schedule = (((5, 0), (0, 3)), ((0, 4), (2, 0)), ((1, 1), (1, 1)))
    row, col = (F(4, 7), F(3, 7), F(0)), (F(2, 7), F(5, 7))
    require(pure_nash(schedule) == set(), "no pure scheduling NE")
    require(is_nash(schedule, row, col), "scheduling full deviation inequalities")
    require(profile_payoff(schedule, row, col) == (F(10, 7), F(12, 7)), "scheduling payoffs")
    require(tuple(row[i]*col[j] for i in (0, 1) for j in (0, 1)) ==
            (F(8, 49), F(20, 49), F(6, 49), F(15, 49)), "joint weights")
    require(pure_deviation_gains(schedule, row, col) == ((F(0), F(0), -F(3, 7)), (F(0), F(0))), "supported ties and Idle loss")
    dominating = (F(1, 3), F(2, 3), F(0))
    require([profile_payoff(schedule, dominating, unit(2, j))[0] for j in range(2)] == [F(5, 3), F(4, 3)], "mixed dominance")
    for better in (0, 1):
        require(not dominates(schedule, 0, better, 2, (0, 1), False), "no pure Idle dominator")
    found = []
    for a in range(8):
        for b in range(8-a):
            rr = (F(a, 7), F(b, 7), F(7-a-b, 7))
            for c in range(8):
                cc = (F(c, 7), F(7-c, 7))
                if is_nash(schedule, rr, cc):
                    found.append((rr, cc))
    require(found == [(row, col)], "complete denominator-seven probability grid")
    checks.append("Scheduling: no pure NE, independent joint-weight payoff sum, all support/off-support inequalities, mixed dominance and 288 rational profiles")

    changed = (((8, 0), (0, 3)), ((0, 4), (2, 0)), ((1, 1), (1, 1)))
    changed_col = (F(1, 5), F(4, 5))
    require(is_nash(changed, row, changed_col), "changed own-payoff NE")
    require(profile_payoff(changed, row, changed_col) == (F(8, 5), F(12, 7)), "changed expected payoffs")
    require(pure_nash(changed) == set(), "changed game no pure NE")
    require([profile_payoff(changed, dominating, unit(2, j))[0] for j in range(2)] == [F(8, 3), F(4, 3)], "changed mixed dominance")
    require(not is_nash(changed, row, col), "old probability detects changed payoff")
    checks.append("Exercise 4: altered payoff forces Left probability 1/5, keeps U probability 4/7, and excludes Idle")

    high_idle = schedule[:2] + (((F(3, 2), 1), (F(3, 2), 1)),)
    require(not is_nash(high_idle, row, col), "off-support improvement detected")
    require(pure_deviation_gains(high_idle, row, col)[0][2] == F(1, 14), "Idle profitable deviation")
    count = 0
    # An exact, bounded probability grid; not a proof of continuum exhaustiveness.
    for a in range(11):
        for b in range(11-a):
            rr = (F(a, 10), F(b, 10), F(10-a-b, 10))
            for c in range(41):
                cc = (F(c, 40), F(40-c, 40))
                expected = a == b == 0 and F(1, 4) <= cc[0] <= F(3, 10)
                require(is_nash(high_idle, rr, cc) == expected, "high-Idle support-family check")
                count += 1
    require(profile_payoff(high_idle, (F(0), F(0), F(1)), (F(1, 4), F(3, 4))) == (F(3, 2), F(1)), "family payoff")
    checks.append(f"Exercise 5: old candidate fails by 1/14; {count} exact profiles check Idle-only equilibrium interval including both endpoints")

    entry = (((0, 8), (0, 8)), ((3, 4), (-2, -1)))
    require(pure_nash(entry) == {(0, 1), (1, 0)}, "entry normal-form NE")
    for e, z in product(range(21), repeat=2):
        entrant = (F(20-e, 20), F(e, 20))
        incumbent = (F(20-z, 20), F(z, 20))
        expected = (e == 0 and z >= 12) or (e == 20 and z == 0)
        require(is_nash(entry, entrant, incumbent) == expected, "entry full mixed family sample")
    entry_nodes = {"root": (0, {"Out": "O", "Enter": "reply"}),
                   "reply": (1, {"A": "A", "F": "F"})}
    entry_terminals = {"O": (0, 8), "A": (3, 4), "F": (-2, -1)}
    credible = plan_key(({"root": "Enter"}, {"reply": "A"}))
    threat = plan_key(({"root": "Out"}, {"reply": "F"}))
    require(tree_equilibria(entry_nodes, entry_terminals, False) == {credible, threat}, "tree normal-form audit")
    require(tree_equilibria(entry_nodes, entry_terminals, True) == {credible}, "subgame deviation removes threat")
    checks.append("Entry: both pure Nash profiles, 441 mixed-profile checks of z>=3/5 family, and independent all-subgame deviation audit")

    for cost in (F(0), F(1), F(7, 2), F(4), F(9, 2), F(5), F(12)):
        nodes, terminals = commitment_tree(cost)
        initial = ("Lock",) if cost < 4 else (("No",) if cost > 4 else ("No", "Lock"))
        expected = {plan_key(({"E_No": "Enter", "E_Lock": "Out"},
                              {"root": first, "I_No": "A"})) for first in initial}
        require(tree_equilibria(nodes, terminals, True) == expected, "irreversible commitment branches/tie")
        if cost == 1:
            require(tree_payoff(nodes, terminals, ({"E_No": "Enter", "E_Lock": "Out"},
                                                 {"root": "Lock", "I_No": "A"})) == (0, 7), "Lock baseline realized payoff")
        nodes, terminals = commitment_tree(cost, reversible=True)
        initial = ("No", "Lock") if cost == 0 else ("No",)
        expected = {plan_key(({"E_No": "Enter", "E_Lock": "Enter"},
                              {"root": first, "I_No": "A", "I_Lock": "A"}))
                    for first in initial}
        require(tree_equilibria(nodes, terminals, True) == expected, "reversible sunk-cost comparison")
    # At c=4 every initial mixture averages equal incumbent payoff, with fixed
    # strict continuation responses. At reversible c=0 the same tie holds.
    for k in range(21):
        probability = F(k, 20)
        require(probability*(8-4)+(1-probability)*4 == 4, "irreversible mixed tie")
        require(probability*(4-0)+(1-probability)*4 == 4, "reversible mixed tie")
    checks.append("Commitment: all pure plans and every subgame deviation at seven costs for both technologies; exact cost-4/cost-0 initial mixing ties")

    coordination = (((6, 3), (0, 0)), ((0, 0), (2, 5)))
    require(pure_nash(coordination) == {(0, 0), (1, 1)}, "coordination pure equilibria")
    coord_row, coord_col = (F(5, 8), F(3, 8)), (F(1, 4), F(3, 4))
    require(is_nash(coordination, coord_row, coord_col), "coordination mixed equilibrium")
    require(profile_payoff(coordination, coord_row, coord_col) == (F(3, 2), F(15, 8)), "coordination payoffs")
    observed_nodes = {"root": (0, {"A": "after_A", "B": "after_B"}),
                      "after_A": (1, {"a": "Aa", "b": "Ab"}),
                      "after_B": (1, {"a": "Ba", "b": "Bb"})}
    observed_terminals = {"Aa": (6, 3), "Ab": (0, 0), "Ba": (0, 0), "Bb": (2, 5)}
    require(len(plans(observed_nodes, 1)) == 4, "four observed contingent strategies")
    expected = {plan_key(({"root": "A"}, {"after_A": "a", "after_B": "b"}))}
    require(tree_equilibria(observed_nodes, observed_terminals, True) == expected, "observed-move SPNE")
    require(tree_payoff(observed_nodes, observed_terminals,
                        ({"root": "A"}, {"after_A": "a", "after_B": "b"})) == (6, 3), "observed outcome")
    # Joining the two column nodes allows only plans aa or bb, corresponding
    # exactly to the two pure columns; ab/ba are unavailable.
    for i, j in product(range(2), repeat=2):
        pp = ({"root": ("A", "B")[i]},
              {"after_A": ("a", "b")[j], "after_B": ("a", "b")[j]})
        require(tree_payoff(observed_nodes, observed_terminals, pp) == coordination[i][j], "hidden action strategic-form reconstruction")
    checks.append("Exercise 8: two pure and one mixed coordination equilibrium, four observed contingent plans, unique observed SPNE, hidden-action strategy restriction")

    retention = (((4, -4), (0, 0)), ((0, 0), (6, -6)))
    probability = (F(3, 5), F(2, 5))
    require(pure_nash(retention) == set(), "retention has no pure equilibrium")
    require(is_nash(retention, probability, probability), "retention mixed best responses")
    require(profile_payoff(retention, probability, probability) == (F(12, 5), -F(12, 5)), "zero-sum retention payoffs")
    checks.append("Delayed check: exact zero-sum mixing/payoffs and cost-5 continuation plan from independent tree enumeration")

    html = CHAPTER.read_text(encoding="utf-8")
    parsed = Structure()
    parsed.feed(html)
    require(not parsed.forbidden, "HTML must be a static fragment")
    require(parsed.worked >= 2 and parsed.exercises == parsed.solutions == 8, "worked/example/solution inventory")
    require("Teach-back" in html and "Delayed check" in html and "Delayed-check answers" in html, "retention instruction/answers")
    require("v05-c06.html" in parsed.links, "canonical prerequisite route")
    require("v05-c08.html" in parsed.links or "curriculum.html#v05-c08" in parsed.links, "successor route")
    require("we do not prove it" in html, "fixed-point proof limit stated")
    sources = json.loads((ROOT / "content/reviews/v05-c07-sources.json").read_text(encoding="utf-8"))
    require(len(sources) == 5 and len({s["id"] for s in sources}) == 5, "five distinct scoped sources")
    require(parsed.sources == {s["id"] for s in sources}, "citation/source proposal match")
    for source in sources:
        require(set(("id", "title", "url", "use", "checked", "verification")) <= set(source), "source record completeness")
        require(source["id"].startswith("v05-c07-") and source["url"] in parsed.links, "source ownership/direct route")
        require(source["checked"] == "2026-10-07", "inspection date")
    checks.append("Static manuscript: three worked examples, eight matching complete solutions, answered retention, five scoped source records and prerequisite/successor routes")
    return {
        "status": "passed",
        "checks": checks,
        "limitations": [
            "Exact finite probability grids diagnose the stated cases; the written support arguments establish the full continuous equilibrium sets.",
            "The tree oracle covers finite perfect-information pure plans. Hidden-information strategy feasibility is checked separately; no general sequential-equilibrium or behavioral/mixed equivalence solver is claimed.",
            "Mixed finite-game existence invokes a fixed-point theorem; this checker does not prove it or certify empirical equilibrium selection.",
            "All payoffs and mechanisms are hypothetical. Complete information, observability, risk neutrality and irreversible commitment are stated model assumptions.",
            "Prerequisite-order acceptance, integrated links/build, external expert review and visual/mobile/print QA remain the coordinator's gates; no UI QA is claimed here.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))

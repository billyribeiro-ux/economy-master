"""Quiet, bounded, independent checks for the four-file Harbor research-audit chapter.

No network, third-party packages, blueprint, prior chapter, or source artifact is read.
The restricted-input API never receives the teaching oracle or full-data output.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import io
import json
import re

HERE = Path(__file__).resolve().parents[1]
HTML_NAME = "content/chapters/v12-c12.html"
SOURCE_NAME = "content/reviews/v12-c12-sources.json"
AUTHOR_NAME = "content/reviews/v12-c12-author.json"
CHECKER_NAME = "scripts/check_v12_c12.py"
SCHEMAS = {
    "frame-baseline.csv": ("unit_id", "trial_participant", "x_stratum"),
    "trial-assignment.csv": ("unit_id", "a"),
    "trial-followup-cents.csv": ("unit_id", "outcome_cents"),
    "auxiliary-notes.csv": ("unit_id", "note_id"),
    "teaching-only-potential-outcomes.csv": ("unit_id", "y0_cents", "y1_cents"),
    "restricted-followup-cents.csv": ("unit_id", "outcome_cents", "access_status"),
}
COUNTS = dict(zip(SCHEMAS, (32, 8, 8, 9, 8, 8)))
SOURCE_IDS = {
    "asa-pvalues-2016", "v04-c01-aea-data-faq",
    "v12-c12-olken-preanalysis2015", "v12-c12-dahabreh-target2019",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite JSON value: " + value)


def strict_json(text):
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_nonfinite)


def _uint(value, maximum, label):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value) is not None,
            label + " must be a canonical nonnegative integer string")
    require(len(value) <= 4, label + " is too long")
    result = int(value)
    require(result <= maximum, label + " is outside the bounded domain")
    return result


def parse_csv(name, text):
    """Parse a declared finite table with strict schema, key and amount checks."""
    require(name in SCHEMAS, "unknown table schema")
    require(type(text) is str and len(text) <= 8000, "CSV must be bounded text")
    require(text.endswith("\n") and "\r" not in text and "\x00" not in text,
            "CSV contract requires LF and a final newline")
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError("malformed CSV") from exc
    require(bool(rows) and tuple(rows[0]) == SCHEMAS[name], "incompatible CSV header")
    require(len(rows) == COUNTS[name] + 1, "wrong table row count")
    result, keys = [], set()
    for cells in rows[1:]:
        require(len(cells) == len(SCHEMAS[name]), "incompatible row width")
        row = dict(zip(SCHEMAS[name], cells))
        upper = 32 if name == "frame-baseline.csv" else 8
        unit = _uint(row["unit_id"], upper, "unit_id")
        require(unit >= 1, "unit_id starts at one")
        row["unit_id"] = unit
        if name == "auxiliary-notes.csv":
            require(re.fullmatch(r"[A-Za-z0-9-]{1,20}", row["note_id"]) is not None,
                    "invalid note ID")
            key = (unit, row["note_id"])
        else:
            key = unit
        require(key not in keys, "duplicate primary key")
        keys.add(key)
        if name == "frame-baseline.csv":
            row["trial_participant"] = _uint(row["trial_participant"], 1, "S")
            row["x_stratum"] = _uint(row["x_stratum"], 1, "X")
        elif name == "trial-assignment.csv":
            row["a"] = _uint(row["a"], 1, "assignment")
        elif name in ("trial-followup-cents.csv", "restricted-followup-cents.csv"):
            if name == "restricted-followup-cents.csv":
                expected_status = "withheld" if unit == 8 else "observed"
                require(row["access_status"] == expected_status, "wrong availability status")
                if unit == 8:
                    require(row["outcome_cents"] == "", "withheld amount must be empty")
                    row["outcome_cents"] = None
                else:
                    row["outcome_cents"] = _uint(row["outcome_cents"], 1200, "outcome")
            else:
                row["outcome_cents"] = _uint(row["outcome_cents"], 1200, "outcome")
        elif name == "teaching-only-potential-outcomes.csv":
            for col in ("y0_cents", "y1_cents"):
                row[col] = _uint(row[col], 1200, col)
        result.append(row)
    if name != "auxiliary-notes.csv":
        require(keys == set(range(1, upper + 1)), "missing or incompatible primary ID set")
    else:
        require({r["unit_id"] for r in result} == set(range(1, 9)), "note coverage")
    return result


def load_trial(raw, completion_cents=None):
    """Return eight correctly joined people and notes from accessible tables only.

    Exact schemas/IDs, integer cents and the declared balanced design are required.
    A restricted table requires an explicitly labeled bounded integer completion.
    No teacher table or previous full-data statistic is accepted by this interface.
    """
    require(type(raw) is dict, "raw tables must be a dictionary")
    common = {"frame-baseline.csv", "trial-assignment.csv", "auxiliary-notes.csv"}
    full, restricted = "trial-followup-cents.csv", "restricted-followup-cents.csv"
    require(set(raw) in (common | {full}, common | {restricted}), "exact accessible table inventory required")
    restricted_mode = restricted in raw
    if restricted_mode:
        require(type(completion_cents) is int and 0 <= completion_cents <= 1200,
                "full-data execution unavailable; supply an explicit integer completion")
    else:
        require(completion_cents is None, "completion is only valid for restricted mode")
    frame = parse_csv("frame-baseline.csv", raw["frame-baseline.csv"])
    assignment = parse_csv("trial-assignment.csv", raw["trial-assignment.csv"])
    notes = parse_csv("auxiliary-notes.csv", raw["auxiliary-notes.csv"])
    outcome_name = restricted if restricted_mode else full
    outcomes = parse_csv(outcome_name, raw[outcome_name])
    frame_map = {r["unit_id"]: r for r in frame}
    participants = {r["unit_id"] for r in frame if r["trial_participant"] == 1}
    require(participants == set(range(1, 9)), "trial participation ID contract")
    require(all(r["x_stratum"] == (0 if r["unit_id"] <= 4 or 9 <= r["unit_id"] <= 14 else 1)
                for r in frame), "fixed frame stratum contract")
    amap = {r["unit_id"]: r["a"] for r in assignment}
    ymap = {r["unit_id"]: r["outcome_cents"] for r in outcomes}
    require(set(amap) == set(ymap) == participants, "core join cardinality")
    require(all(sum(amap[i] for i in participants if frame_map[i]["x_stratum"] == x) == 2
                for x in (0, 1)), "assignment must treat exactly two in each stratum")
    if restricted_mode:
        ymap[8] = completion_cents
    joined = tuple({"unit_id": i, "x": frame_map[i]["x_stratum"], "a": amap[i],
                    "y": F(ymap[i], 100)} for i in sorted(participants))
    return joined, notes


def _csv(name, rows):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(SCHEMAS[name])
    writer.writerows(rows)
    return stream.getvalue()


def primitive_fixtures():
    """Independent encoding of the study's primitive law, not saved results."""
    b = (1, 2, 3, 4, 2, 4, 6, 8)
    effects = (1, 1, 1, 1, 3, 3, 3, 3)
    treated = {3, 4, 7, 8}
    frame = [(i, int(i <= 8), int(not (i <= 4 or 9 <= i <= 14))) for i in range(1, 33)]
    a = [(i, int(i in treated)) for i in range(1, 9)]
    y = [(i, 100 * (b[i - 1] + int(i in treated) * effects[i - 1])) for i in range(1, 9)]
    notes = [(i, "note-" + str(i)) for i in range(1, 8)] + [(8, "note-8a"), (8, "note-8b")]
    potentials = [(i, 100 * b[i - 1], 100 * (b[i - 1] + effects[i - 1])) for i in range(1, 9)]
    redacted = [(i, amount if i != 8 else "", "observed" if i != 8 else "withheld") for i, amount in y]
    return dict(zip(SCHEMAS, (_csv(name, rows) for name, rows in zip(SCHEMAS,
                        (frame, a, y, notes, potentials, redacted)))))


def mean(values):
    require(len(values) > 0, "empty mean")
    return sum(values, F(0)) / len(values)


def variance(values, sample=False):
    require(len(values) > int(sample), "variance needs observations")
    avg = mean(values)
    return sum((x - avg) ** 2 for x in values) / (len(values) - int(sample))


def cell_contrasts(rows):
    return tuple(mean([r["y"] for r in rows if r["x"] == x and r["a"] == 1]) -
                 mean([r["y"] for r in rows if r["x"] == x and r["a"] == 0]) for x in (0, 1))


def weighted_contrast(rows, weights):
    return sum(q * d for q, d in zip(weights, cell_contrasts(rows)))


def neyman(rows, weights):
    return sum(weights[x] ** 2 * sum(variance([r["y"] for r in rows if r["x"] == x and r["a"] == a],
                                            sample=True) / 2 for a in (0, 1)) for x in (0, 1))


def assignments():
    return tuple(tuple(int(i in low + high) for i in range(8))
                 for low in combinations(range(4), 2) for high in combinations(range(4, 8), 2))


def fmt(value):
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(fmt(x) for x in value) + ")"
    return str(value).replace("-", "−")


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.examples, self.exercises, self.solutions, self.sources = [], [], [], [], []
        self.fixtures, self.calcs = {}, {}
        self.fixture = self.calc = None
        self.fixture_text, self.calc_text = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if "worked" in a.get("class", "").split():
            self.examples.append(a.get("id"))
        if tag == "li" and re.fullmatch(r"v12-c12-e[0-9]+", a.get("id", "")):
            self.exercises.append(a["id"])
        if "data-solution-for" in a:
            self.solutions.append(a["data-solution-for"])
        if "data-source" in a:
            self.sources.append(a["data-source"])
        if "data-fixture" in a:
            require(tag == "pre" and self.fixture is None, "fixture structure")
            self.fixture, self.fixture_text = a["data-fixture"], []
        if "data-calc" in a:
            require(tag == "span" and self.calc is None, "numeric anchor structure")
            self.calc, self.calc_text = a["data-calc"], []

    def handle_data(self, text):
        if self.fixture is not None:
            self.fixture_text.append(text)
        if self.calc is not None:
            self.calc_text.append(text)

    def handle_endtag(self, tag):
        if tag == "pre" and self.fixture is not None:
            require(self.fixture not in self.fixtures, "duplicate fixture")
            self.fixtures[self.fixture] = "".join(self.fixture_text)
            self.fixture = None
        if tag == "span" and self.calc is not None:
            require(self.calc not in self.calcs, "duplicate calculation anchor")
            self.calcs[self.calc] = "".join(self.calc_text).strip()
            self.calc = None


class Audit:
    def __init__(self):
        self.comparisons = 0
        self.rejections = 0

    def eq(self, actual, expected, label):
        require(actual == expected, "check failed: " + label + "; got " + repr(actual) + ", expected " + repr(expected))
        self.comparisons += 1

    def rejects(self, function, label):
        try:
            function()
        except ValueError:
            self.rejections += 1
        else:
            raise ValueError("invalid input accepted: " + label)


def _mutate_cell(text, row, column, value):
    rows = list(csv.reader(io.StringIO(text)))
    rows[row][column] = value
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerows(rows)
    return out.getvalue()


def check():
    """Validate exactly four canonical payloads; return a deterministic JSON-safe summary."""
    audit = Audit()
    author = strict_json((HERE / AUTHOR_NAME).read_text(encoding="utf-8"))
    sources = strict_json((HERE / SOURCE_NAME).read_text(encoding="utf-8"))
    bindings = author["payload_bindings"]
    audit.eq({b["path"] for b in bindings}, {HTML_NAME, CHECKER_NAME, SOURCE_NAME}, "three nonself payloads")
    audit.eq(len(bindings), 3, "binding count")
    for binding in bindings:
        path = HERE / binding["path"]
        data = path.read_bytes()
        audit.eq((len(data), hashlib.sha256(data).hexdigest()),
                 (binding["bytes"], binding["sha256"]), "payload binding " + path.name)
    audit.eq(sources["chapter"], "v12-c12", "source chapter")
    audit.eq({r["id"] for r in sources["sources"]}, SOURCE_IDS, "source scope IDs")
    audit.eq(sources["source_reading_boundary"]["new_primary_reads_by_this_author"], 0, "inspection attribution")
    text = (HERE / HTML_NAME).read_text(encoding="utf-8")
    doc = Document()
    doc.feed(text)
    doc.close()
    audit.eq(len(doc.ids), len(set(doc.ids)), "unique HTML IDs")
    audit.eq(doc.examples, ["v12-c12-case" + str(i) for i in range(1, 7)], "six worked cases")
    audit.eq(doc.exercises, ["v12-c12-e" + str(i) for i in range(1, 13)], "twelve exact prompts")
    audit.eq(doc.solutions, doc.exercises, "twelve paired complete solutions")
    audit.eq(set(doc.sources), SOURCE_IDS, "manuscript source routes")
    audit.eq('class="exercises"' in text and 'class="solutions"' in text, True, "shared reader classes")
    audit.eq("Teach-back and delayed retention" in text, True, "retention heading")
    raw = primitive_fixtures()
    audit.eq(set(doc.fixtures), set(raw), "six visible fixture inventory")
    for name in raw:
        audit.eq(doc.fixtures[name], raw[name], "independently reconstructed raw fixture " + name)
        audit.eq(len(parse_csv(name, raw[name])), COUNTS[name], "valid table " + name)
    accessible = {name: raw[name] for name in ("frame-baseline.csv", "trial-assignment.csv",
                                             "trial-followup-cents.csv", "auxiliary-notes.csv")}
    restricted = {k: v for k, v in accessible.items() if k != "trial-followup-cents.csv"}
    restricted["restricted-followup-cents.csv"] = raw["restricted-followup-cents.csv"]
    rows, notes = load_trial(accessible)
    oracle = parse_csv("teaching-only-potential-outcomes.csv", raw["teaching-only-potential-outcomes.csv"])
    potentials = {r["unit_id"]: (F(r["y0_cents"], 100), F(r["y1_cents"], 100)) for r in oracle}
    for r in rows:
        audit.eq(r["y"], potentials[r["unit_id"]][r["a"]], "actual observed consistency")
    omega = assignments()
    half, target_weights = (F(1, 2), F(1, 2)), (F(1, 4), F(3, 4))
    design_values, design_vhat, target_values, target_vhat = [], [], [], []
    for z in omega:
        generated = tuple({"unit_id": i + 1, "x": int(i >= 4), "a": z[i], "y": potentials[i + 1][z[i]]}
                          for i in range(8))
        design_values.append(weighted_contrast(generated, half))
        design_vhat.append(neyman(generated, half))
        target_values.append(weighted_contrast(generated, target_weights))
        target_vhat.append(neyman(generated, target_weights))
        audit.eq(sum(z[:4]) == sum(z[4:]) == 2, True, "whole-vector balance")
    for i in range(8):
        audit.eq(mean([F(z[i]) for z in omega]), F(1, 2), "one-person inclusion")
        for j in range(i + 1, 8):
            audit.eq(mean([F(z[i] * z[j]) for z in omega]),
                     F(1, 6) if i // 4 == j // 4 else F(1, 4), "pair inclusion covariance input")
    base_variances = tuple(variance([potentials[i][0] for i in range(1 + 4*x, 5 + 4*x)], sample=True) for x in (0, 1))
    audit.eq(variance(design_values), sum(q*q*v for q, v in zip(half, base_variances)), "design covariance versus enumeration")
    audit.eq(mean(design_vhat), variance(design_values), "Neyman expectation under declared effects")
    audit.eq(variance(target_values), sum(q*q*v for q, v in zip(target_weights, base_variances)), "target covariance versus enumeration")
    audit.eq(mean(target_vhat), variance(target_values), "target Neyman expectation")
    contrasts = cell_contrasts(rows)
    observed = weighted_contrast(rows, half)
    truth = mean([b - a for a, b in potentials.values()])
    row_map = {r["unit_id"]: r for r in rows}
    duplicated = tuple(row_map[n["unit_id"]] for n in notes)
    duplicate_pooled = mean([r["y"] for r in duplicated if r["a"]]) - mean([r["y"] for r in duplicated if not r["a"]])
    # Frozen outcomes under sharp zero: deliberately no potential-outcome regeneration.
    y = tuple(r["y"] for r in rows)
    null_values = tuple(sum((2*z[i]-1)*y[i] for i in range(8)) / 4 for z in omega)
    null_pmf = Counter(null_values)
    abs_p = tuple(F(sum(abs(v) >= abs(t) for v in null_values), len(omega)) for t in null_values)
    selected_p = tuple(F(sum(v >= t if t >= 0 else v <= t for v in null_values), len(omega)) for t in null_values)
    calibrated_p = tuple(F(sum(p <= observed_p for p in selected_p), len(omega)) for observed_p in selected_p)
    actual_z = tuple(r["a"] for r in rows)
    index = omega.index(actual_z)
    for i, z in enumerate(omega):
        complement_index = omega.index(tuple(1-a for a in z))
        audit.eq(null_values[complement_index], -null_values[i], "complement reflection")
        audit.eq(calibrated_p[i], abs_p[i], "full direction-rule calibration")
    for level in sorted(set(abs_p)):
        audit.eq(F(sum(p <= level for p in abs_p), 36) <= level, True, "finite inclusive tail validity")
    audit.eq(min(abs_p), F(2, len(omega)), "two-sided lattice floor")
    audit.eq(mean(null_values), F(0), "sharp-null mean")
    fixed_y_variances = tuple(variance(list(y[4*x:4*x+4]), sample=True) for x in (0, 1))
    audit.eq(variance(null_values), sum(q*q*v for q, v in zip(half, fixed_y_variances)), "null covariance versus enumeration")
    # Finite frame: I is conceptual uniform, Z remains a dependent balanced vector.
    frame = parse_csv("frame-baseline.csv", raw["frame-baseline.csv"])
    cell_counts = Counter((r["trial_participant"], r["x_stratum"]) for r in frame)
    participant_counts = tuple(cell_counts[(1,x)] for x in (0,1))
    target_counts = tuple(cell_counts[(0,x)] for x in (0,1))
    total_target = sum(target_counts)
    p = tuple(F(participant_counts[x], participant_counts[x]+target_counts[x]) for x in (0,1))
    odds = tuple((1-a)/a for a in p)
    treatment_weights = tuple(2*o for o in odds)
    m = tuple(tuple(mean([potentials[i][a] for i in range(1+4*x,5+4*x)]) for x in (0,1)) for a in (0,1))
    population_levels = tuple(sum(F(target_counts[x],total_target)*m[a][x] for x in (0,1)) for a in (0,1))
    weighted_totals = tuple(sum(treatment_weights[r["x"]]*r["y"] for r in rows if r["a"]==a) for a in (0,1))
    sample_levels = tuple(v/total_target for v in weighted_totals)
    for z in omega:
        for a in (0,1):
            audit.eq(sum(treatment_weights[i//4] for i in range(8) if z[i]==a), F(total_target), "fixed treatment denominator")
    # Sum over conceptual I and whole Z directly, a method distinct from target standardization.
    for a in (0,1):
        direct = sum(2*odds[(i-1)//4]*potentials[i][a] for z in omega for i in range(1,9) if z[i-1]==a)
        direct /= len(omega)*total_target
        audit.eq(direct, population_levels[a], "finite joint-law inverse odds identity")
    audit.eq(mean(target_values), population_levels[1]-population_levels[0], "unbiased target effect")
    pooled_weights = tuple(F(participant_counts[x]+target_counts[x],len(frame)) for x in (0,1))
    effects = tuple(m[1][x]-m[0][x] for x in (0,1))
    shifted_levels = tuple(sum(target_weights[x]*(m[a][x]+(1,-2)[x]) for x in (0,1)) for a in (0,1))
    shift_vertices = tuple(sum(target_weights[x]*(effects[x]+d[x]) for x in (0,1))
                           for d in ((F(-1,2),-1),(F(-1,2),1),(F(1,2),-1),(F(1,2),1)))
    sensitivity = min(shift_vertices),max(shift_vertices)
    supported = F(1,5)*effects[0]+F(3,5)*effects[1]
    unsupported = supported-F(12,5), supported+F(12,5)
    audit.eq(shifted_levels[1]-shifted_levels[0], population_levels[1]-population_levels[0], "effect-only shifts preserve effect")
    for lam in (F(0),F(1,4),F(1,2),F(1)):
        delta = ((1-lam)*F(-1,2)+lam*F(1,2),(1-lam)*(-1)+lam)
        audit.eq(sum(target_weights[x]*(effects[x]+delta[x]) for x in (0,1)),
                 (1-lam)*sensitivity[0]+lam*sensitivity[1], "sharp effect-shift witness")
        new_cell_effect = (1-lam)*(-12)+lam*12
        audit.eq(supported+F(1,5)*new_cell_effect,(1-lam)*unsupported[0]+lam*unsupported[1],"unsupported mixture witness")
    # Restricted world uses exactly seven known amounts plus assignments/strata/bounds.
    redacted_rows = parse_csv("restricted-followup-cents.csv", raw["restricted-followup-cents.csv"])
    known_cents = tuple(r["outcome_cents"] for r in redacted_rows[:7])
    affine = tuple((sum((2*z[i]-1)*known_cents[i] for i in range(7)),2*z[7]-1) for z in omega)
    class_counts = Counter()
    c_values = Counter()
    for m_cents,s in affine:
        c = F(m_cents*s,100)
        c_values[c] += 1
        if c >= 9:
            class_counts["always"] += 1
        elif c <= -9:
            class_counts["w<="+str((-c-9)/2)] += 1
        else:
            class_counts["never"] += 1
    audit.eq(class_counts,Counter({"always":2,"never":20,"w<=0":4,"w<=1":4,"w<=2":4,"w<=4":2}),"affine comparison classes")
    audit.eq({c:n for c,n in c_values.items() if c<=-9 or c>=9},
             {F(9):2,F(-17):2,F(-13):4,F(-11):4,F(-9):4},"printed affine c classes")
    grid_p, grid_stat = Counter(), []
    for k in range(1201):
        numerator = sum(abs(m_cents+s*k) >= 900+k for m_cents,s in affine)
        tail = F(numerator,36)
        expected = F(4,9) if k==0 else F(1,3) if k<=100 else F(2,9) if k<=200 else F(1,9) if k<=400 else F(1,18)
        audit.eq(tail,expected,"cent completion inclusive partition")
        grid_p[tail] += 1
        grid_stat.append(F(900+k,400))
    audit.eq(len(set(grid_stat)),1201,"exact distinct completion lattice")
    audit.eq(set(b-a for a,b in zip(grid_stat,grid_stat[1:])),{F(1,400)},"completion step")
    audit.eq(grid_p,Counter({F(4,9):1,F(1,3):100,F(2,9):100,F(1,9):200,F(1,18):800}),"p-region grid multiplicities")
    for k in (0,100,101,200,201,400,401,1200):
        completed,_ = load_trial(restricted,completion_cents=k)
        audit.eq(weighted_contrast(completed,half),F(900+k,400),"restricted executable completion")
    complete_case_rows = tuple(r for r in rows if r["unit_id"]!=8)
    # Focused transfer checks: order, units, constant shifts/ties, weights, and the unavailable-information interface.
    shuffled = deepcopy(accessible)
    for name in shuffled:
        lines=shuffled[name].splitlines()
        shuffled[name]="\n".join([lines[0]]+list(reversed(lines[1:])))+"\n"
    shuffled_rows,_=load_trial(shuffled)
    audit.eq(shuffled_rows,rows,"row order is not person identity")
    for factor, shift in ((F(1,2),0),(F(1),100)):
        modified=deepcopy(accessible)
        csvrows=list(csv.reader(io.StringIO(modified["trial-followup-cents.csv"])))
        for r in csvrows[1:]:
            amount=factor*int(r[1])+shift
            require(amount.denominator==1,"intervention must preserve integer cents")
            r[1]=str(amount.numerator)
        modified["trial-followup-cents.csv"]=_csv("trial-followup-cents.csv",csvrows[1:])
        changed,_=load_trial(modified)
        audit.eq(weighted_contrast(changed,half),factor*observed,"unit scaling or common shift")
        newnull=tuple(sum((2*z[i]-1)*changed[i]["y"] for i in range(8))/4 for z in omega)
        audit.eq(tuple(F(sum(abs(v)>=abs(t) for v in newnull),36) for t in newnull),abs_p,"scale/translation randomization invariance")
    tied=[F(7)]*8
    tie_orbit=tuple(sum((2*z[i]-1)*tied[i] for i in range(8))/4 for z in omega)
    audit.eq(set(tie_orbit),{F(0)},"all-constant outcome ties")
    audit.eq(F(sum(abs(v)>=0 for v in tie_orbit),36),F(1),"ties included at one")
    for q in ((F(1),F(0)),(F(0),F(1))):
        x=0 if q[0] else 1
        audit.eq(weighted_contrast(rows,q),contrasts[x],"target endpoint stratum")
        audit.eq(sum(a*a*v for a,v in zip(q,base_variances)),base_variances[x],"target endpoint variance")
    # Every displayed data-calc anchor is matched to a independently derived quantity.
    anchors={
        "assignment-count":len(omega),"observed-contrasts":contrasts,"observed-primary":observed,
        "trial-effect":truth,"duplicate-pooled":duplicate_pooled,"duplicate-high":cell_contrasts(duplicated)[1],
        "duplicate-stratified":weighted_contrast(duplicated,half),"baseline-stratum-variances":base_variances,
        "trial-variance":variance(design_values),"observed-neyman":neyman(rows,half),"mean-neyman":mean(design_vhat),
        "null-variance":variance(null_values),"two-sided-p":abs_p[index],"selected-p":selected_p[index],
        "selected-size":F(sum(p<=F(1,20) for p in selected_p),36),
        "selected-zero":selected_p[null_values.index(F(0))],"calibrated-p":calibrated_p[index],
        "participation":p,"target-levels":population_levels,"target-effect":population_levels[1]-population_levels[0],
        "inverse-odds":odds,"treatment-weight-total":sum(treatment_weights[r["x"]] for r in rows if r["a"]),
        "weighted-outcome-totals":weighted_totals,"target-sample-levels":sample_levels,
        "target-sample-effect":sample_levels[1]-sample_levels[0],"target-variance":variance(target_values),
        "target-neyman":neyman(rows,target_weights),"weight-diagnostic":sum(participant_counts[x]*odds[x] for x in (0,1))/total_target,
        "pooled-population-effect":sum(pooled_weights[x]*effects[x] for x in (0,1)),
        "pooled-sample-effect":weighted_contrast(rows,pooled_weights),"shifted-levels":shifted_levels,
        "effect-sensitivity":"["+str(sensitivity[0])+","+str(sensitivity[1])+"]",
        "unsupported-bound":"["+str(unsupported[0])+","+str(unsupported[1])+"]",
        "completion-lattice":"{9/4+k/400:k=0,...,1200}","completion-count":len(grid_stat),
        "completion-envelope":"["+str(min(grid_stat))+","+str(max(grid_stat))+"]",
        "zero-imputation":grid_stat[0],"complete-case":weighted_contrast(complete_case_rows,half),
        "completion-p-set":"{"+",".join(str(p) for p in sorted(grid_p))+"}",
    }
    audit.eq(set(doc.calcs),set(anchors),"complete numeric anchor inventory")
    for key,value in anchors.items():
        audit.eq(doc.calcs[key],fmt(value),"printed number "+key)
    # Deliberately malformed domains; no assertion statements or -O-sensitive validation.
    for invalid in (None, [], True):
        audit.rejects(lambda invalid=invalid:load_trial(invalid),"table container")
    for removed in accessible:
        bad=deepcopy(accessible);del bad[removed]
        audit.rejects(lambda bad=bad:load_trial(bad),"missing primary table")
    bad=deepcopy(accessible);bad["teaching-only-potential-outcomes.csv"]=raw["teaching-only-potential-outcomes.csv"]
    audit.rejects(lambda:load_trial(bad),"oracle cannot enter analyst API")
    for value in ("", "NaN", "1.5", "-1", "+1", " 100", "0100", "1201"):
        bad=deepcopy(accessible)
        bad["trial-followup-cents.csv"]=_mutate_cell(bad["trial-followup-cents.csv"],1,1,value)
        audit.rejects(lambda bad=bad:load_trial(bad),"invalid cents "+repr(value))
    for name,row,col,value in (
        ("trial-followup-cents.csv",8,0,"7"),
        ("trial-assignment.csv",8,0,"9"),
        ("trial-assignment.csv",1,1,"1"),
        ("frame-baseline.csv",1,1,"0"),
        ("frame-baseline.csv",1,2,"1"),
        ("auxiliary-notes.csv",9,1,"note-8a"),
        ("auxiliary-notes.csv",9,1,"bad note"),
    ):
        bad=deepcopy(accessible);bad[name]=_mutate_cell(bad[name],row,col,value)
        audit.rejects(lambda bad=bad:load_trial(bad),"invalid IDs, design or notes")
    for altered in (raw["trial-followup-cents.csv"].replace("outcome_cents","amount"),
                    raw["trial-followup-cents.csv"].replace("1,100\n","1,100,extra\n"),
                    raw["trial-followup-cents.csv"].replace("8,1100\n",""),
                    raw["trial-followup-cents.csv"].replace("\n","\r\n"),
                    raw["trial-followup-cents.csv"][:-1]):
        bad=deepcopy(accessible);bad["trial-followup-cents.csv"]=altered
        audit.rejects(lambda bad=bad:load_trial(bad),"invalid schema/row shape")
    audit.rejects(lambda:parse_csv("unknown",raw["trial-followup-cents.csv"]),"unknown table")
    audit.rejects(lambda:parse_csv("trial-followup-cents.csv",True),"nontext table")
    for completion in (None, True, 0.0, -1, 1201, "100"):
        audit.rejects(lambda completion=completion:load_trial(restricted,completion),"unavailable or invalid completion")
    audit.rejects(lambda:load_trial(accessible,100),"unrequested completion")
    for row,col,value in ((8,1,"1100"),(7,1,""),(8,2,"observed")):
        bad=deepcopy(restricted);name="restricted-followup-cents.csv"
        bad[name]=_mutate_cell(bad[name],row,col,value)
        audit.rejects(lambda bad=bad:load_trial(bad,100),"incompatible restricted record")
    for malformed in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
        audit.rejects(lambda malformed=malformed:strict_json(malformed),"strict JSON")
    summary={"chapter":"v12-c12","status":"author checks passed; independent peer pending",
             "comparisons":audit.comparisons,"domain_rejections":audit.rejections,
             "visible_csv_fixtures":len(raw),"numeric_anchors":len(anchors),
             "actual_assignments":len(omega),"null_assignments":len(null_values),
             "restricted_cent_completions":len(grid_stat),"focused_transfer_groups":8,
             "worked_cases":len(doc.examples),"solved_exercises":len(doc.solutions),
             "trial_mean":str(mean(design_values)),"trial_variance":str(variance(design_values)),
             "sharp_zero_p":str(abs_p[index]),"target_effect_mean":str(mean(target_values)),
             "restricted_p_counts":{str(k):v for k,v in sorted(grid_p.items())},
             "runtime_payloads":4}
    json.dumps(summary,allow_nan=False)
    return summary


if __name__ == "__main__":
    check()

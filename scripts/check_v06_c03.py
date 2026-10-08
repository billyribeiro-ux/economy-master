"""Independent exact audit for v06-c03. Quiet check() returns JSON evidence.

Closed-form paths and direct finite moments provide separate reference paths
from the downloadable loop program. No network, packages or book mutations.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "content/projects"
INPUT = PROJECT / "v06-c03-models.json"
PROGRAM = PROJECT / "v06-c03-dynamics.py"


def require(value, label):
    if not value:
        raise AssertionError(label)


def objective(r, a, eta, d):
    return a*(1-r)+d*a*(1+eta*r/(1+r))


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.worked = self.exercises = self.solutions = 0
        self.exercise_list = self.solution_details = False
        self.downloads, self.sources, self.forbidden = [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"html", "body", "h1", "script"}:
            self.forbidden.append(tag)
        if tag == "aside" and attrs.get("class") == "worked":
            self.worked += 1
        if tag == "ol" and attrs.get("class") == "exercises":
            self.exercise_list = True
        if tag == "details" and attrs.get("class") == "solutions":
            self.solution_details = True
        if tag == "li":
            self.exercises += self.exercise_list
            self.solutions += self.solution_details
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs.get("href", ""))
        if "data-source" in attrs:
            self.sources.add(attrs["data-source"])

    def handle_endtag(self, tag):
        if tag == "ol":
            self.exercise_list = False
        if tag == "details":
            self.solution_details = False


def check():
    checks = []
    grid = [F(i, 100) for i in range(101)]
    # Interior loss identity is algebraically distinct from FOC calculation.
    for a, eta, d, optimum, target in [
        (F(100), F(9, 4), F(1), F(1, 2), F(225)),
        (F(80), F(4), F(9, 16), F(1, 2), F(145)),
        (F(80), F(25, 16), F(1), F(1, 4), F(165)),
    ]:
        require(d*eta == (1+optimum)**2, "stationary root")
        require(objective(optimum, a, eta, d) == target, "research value")
        for r in grid:
            require(target-objective(r, a, eta, d) == a*(r-optimum)**2/(1+r),
                    "exact global interior loss identity")
    for k, optimum in [(F(1, 2), F(0)), (F(1), F(0)), (F(4), F(1)), (F(5), F(1))]:
        for r in grid:
            slope = -1+k/(1+r)**2
            require(slope <= 0 if optimum == 0 else slope >= 0, "endpoint slope domain")
            require(objective(optimum, F(1), k, F(1)) >= objective(r, F(1), k, F(1)),
                    "endpoint global comparison")
    require(objective(F(0), F(80), F(4), F(9, 16)) == 125 and
            objective(F(1), F(80), F(4), F(9, 16)) == 135, "exercise endpoints")
    private_r, theta, eta = F(1, 4), F(25, 36), F(9, 4)
    increment = F(100)*eta*private_r/(1+private_r)
    require(increment == 45 and theta*increment-100*private_r == F(25, 4) and
            (1-theta)*increment == F(55, 4), "appropriation arithmetic")
    require(theta*eta == (1+private_r)**2 and F(4, 9)*eta == 1, "private optimum threshold")
    for r in grid:
        payoff = -100*r+theta*100*eta*r/(1+r)
        require(F(25, 4)-payoff == 100*(r-private_r)**2/(1+r), "private global loss")
    checks.append("Research: three independent interior loss identities, two boundary thresholds, four endpoint domains and private/social appropriation arithmetic")

    for h in (F(0), F(1), F(2), F(4)):
        for r in grid:
            g = F(3, 2)*r*h/(1+r*h)
            require(0 <= g <= F(3, 2)*h/(1+h) < F(3, 2), "bounded increment")
    require(F(80)*(1+F(1, 2))**2 == 180, "innovation path exercise")
    # Accounting observational equivalence, squared to avoid floating roots.
    require(F(100)*F(4)*F(1) == F(100)*F(1)*F(4) == F(20)**2,
            "same output with technology versus skills")
    for e in grid:
        require(F(2)-8*e*(1-e) == 8*(e-F(1, 2))**2, "steady schooling optimum")
    require([2-F(3, 4)**t for t in range(4)] == [F(1), F(5, 4), F(23, 16), F(101, 64)],
            "skill closed form")
    checks.append("Accounting ambiguity, bounded innovation at zero/positive skills, geometric knowledge path and exact steady-schooling loss identity")

    original_hash = sha256(INPUT.read_bytes()).hexdigest()
    data = json.loads(INPUT.read_text())
    spec = importlib.util.spec_from_file_location("v06_c03_benchmark", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    quiet = io.StringIO()
    with redirect_stdout(quiet):
        spec.loader.exec_module(module)
        result = module.analyze(data)
    require(not quiet.getvalue(), "quiet import and callable")
    require(result == json.loads((PROJECT / "v06-c03-output.json").read_text()), "preserved exact output")
    for source, output in zip(data["research"], result["research"]):
        a, eta, d, theta = [F(source[k]) for k in ("A0", "eta", "d", "theta")]
        for row in output["candidates"]:
            r = F(row["r"])
            require(F(row["J"]) == objective(r, a, eta, d), "independent dated research value")
            require(F(row["Y0"]) == a*(1-r) and F(row["Y1"]) == a*(1+(eta*r)/(1+r)),
                    "dated goods units")
    require(result["research"][0]["best_supplied_social"] == ["1/2"] and
            result["research"][0]["best_supplied_private"] == ["1/4"], "candidate selection scope")
    require(result["innovation_path"]["A"] == ["80", "120", "180"], "download innovation output")

    for source, output in zip(data["schooling"], result["schooling"]):
        initial, delta, chi, e = [F(source[k]) for k in ("h0", "delta", "chi", "e")]
        expected = [(chi*e/delta)+(1-delta)**t*(initial-chi*e/delta) if delta else initial+t*chi*e
                    for t in range(source["periods"]+1)]
        require(list(map(F, output["h"])) == expected, "schooling loop versus closed form")
        require(output["unique_fixed_point"] == (str(chi*e/delta) if delta else None),
                "schooling fixed-point boundary")
    changed = deepcopy(data["schooling"][0])
    changed["delta"] = "1"
    require(module.schooling(changed)["h"][1:] == [F(1, 2)]*3, "full skill depreciation")
    changed.update(delta="0", e="0")
    require(module.schooling(changed)["boundary"] == "every h is fixed", "zero depreciation and education")
    checks.append("Benchmark research values and schooling recursions checked against independent exact closed forms, including zero/full depreciation boundaries")

    for source, output in zip(data["diffusion"], result["diffusion"]):
        f0, a0, h, kappa, g = [F(source[k]) for k in ("F0", "A0", "h", "kappa", "g")]
        lam = h/(kappa+h)
        rho = (1-lam)/(1+g)
        fixed = lam/(lam+g) if lam+g else None
        require(F(output["rho"]) == rho and output["unique_relative_fixed_point"] ==
                (str(fixed) if fixed is not None else None), "diffusion fixed point and denominator")
        for t, row in enumerate(output["path"]):
            ratio = fixed+rho**t*(a0/f0-fixed) if fixed is not None else a0/f0
            frontier = f0*(1+g)**t
            require(F(row["relative_A"]) == ratio and F(row["F"]) == frontier and
                    F(row["A"]) == ratio*frontier, "aggregate loop versus ratio closed form")
            require(0 <= ratio <= 1, "invariant frontier bound")
    require(result["diffusion"][0]["path"][1]["relative_A"] == "14/25" and
            result["diffusion"][0]["path"][2]["relative_A"] == "78/125", "worked diffusion targets")
    require(result["diffusion"][1]["unique_relative_fixed_point"] == "8/11" and
            result["diffusion"][1]["path"][1]["relative_A"] == "16/25", "higher skill exercise")
    require(result["diffusion"][2]["path"][1]["relative_A"] == "2/5", "delayed ratio")
    changed = deepcopy(data["diffusion"][0])
    changed.update(g="0", periods=10)
    stationary = module.diffusion(changed)
    require(stationary["unique_relative_fixed_point"] == 1 and
            stationary["path"][-1]["relative_A"] == 1-F(3, 5)*F(1, 2)**10,
            "stationary frontier catch-up")
    changed.update(A0="100", g="1/4", periods=1)
    require(module.diffusion(changed)["path"][1]["relative_A"] == F(4, 5),
            "old-frontier timing at initial frontier")
    checks.append("Five diffusion paths matched ratio closed forms; no absorption, static frontier, zero/zero fixed-point nonuniqueness and old-frontier timing audited")

    zs, vs = [F(-1), F(-1), F(1), F(1)], [F(-1), F(1), F(-1), F(1)]
    rs, ys = list(map(F, (1, 3, -3, -1))), [F(1, 2), F(3, 2), F(-3, 2), F(-1, 2)]
    require(sum(rs) == sum(ys) == sum(zs) == 0, "centered synthetic variables")
    covariance_r = sum(z*r for z, r in zip(zs, rs))/4
    covariance_y = sum(z*y for z, y in zip(zs, ys))/4
    require(covariance_r == -2 and covariance_y == -1, "direct IV products")
    for z, v, r, y in zip(zs, vs, rs, ys):
        require(F(1, 5)*r-F(3, 5)*z+F(3, 10)*v == y, "observational equivalence")
        require((F(1, 5)*(r+1)-F(3, 5)*z+F(3, 10)*v)-y == F(1, 5),
                "intervention holds structural inputs fixed")
    iv = result["iv"]
    require(iv["cov_Z_R"] == "-2" and iv["cov_Z_y1"] == iv["cov_Z_y2"] == "-1" and
            iv["cov_Z_u2"] == "-3/5" and iv["iv1"] == iv["iv2"] == "1/2" and
            iv["same_observables"] is True and iv["intervention_effect2"] == "1/5", "IV output")
    require(F(1, 5)+F(-3, 5)/F(-2) == F(1, 2), "generic direct-channel bias")
    changed = deepcopy(data)
    changed["iv"]["gamma"] = "0"
    require(module.analyze(changed)["iv"]["same_observables"] is False, "changed direct channel detected")
    changed["iv"]["pi"] = "0"
    require(module.analyze(changed)["iv"]["iv1"] is None, "irrelevant instrument denominator")
    checks.append("All four IV states, direct covariance sums, identical observational distributions, distinct intervention responses, exclusion failure and relevance boundary")

    # Mutations exercise model contracts, not merely the implementation's own identities.
    invalid = []
    for group, key, value in [("research", "A0", "0"), ("research", "theta", "2"),
                              ("research", "d", "0"), ("schooling", "delta", "-1/4"),
                              ("schooling", "e", "2"), ("schooling", "periods", True),
                              ("diffusion", "A0", "101"), ("diffusion", "kappa", "0"),
                              ("diffusion", "g", "-1/4"), ("diffusion", "periods", 101),
                              ("research", "eta", 2.25), ("research", "eta", True),
                              ("research", "eta", "1/0")]:
        mutant = deepcopy(data)
        mutant[group][0][key] = value
        invalid.append(mutant)
    mutant = deepcopy(data)
    mutant["research"][0]["candidates"] = ["0", "0"]
    invalid.append(mutant)
    mutant = deepcopy(data)
    mutant["schema"] = "unknown"
    invalid.append(mutant)
    with tempfile.TemporaryDirectory() as directory:
        run = subprocess.run([sys.executable, str(PROGRAM)], cwd=directory, capture_output=True, text=True)
        require(run.returncode == 0 and not run.stderr and json.loads(run.stdout) == result,
                "standalone default from unrelated working directory")
        for i, mutant in enumerate(invalid):
            try:
                module.analyze(mutant)
            except (ValueError, TypeError, KeyError, ZeroDivisionError):
                pass
            else:
                raise AssertionError(f"invalid input accepted: {i}")
            file = Path(directory) / f"invalid-{i}.json"
            file.write_text(json.dumps(mutant))
            run = subprocess.run([sys.executable, str(PROGRAM), str(file)], capture_output=True, text=True)
            require(run.returncode != 0 and not run.stdout and "error:" in run.stderr,
                    "invalid CLI input fails visibly")
    changed = deepcopy(data)
    changed["research"][0]["candidates"] = ["0", "1"]
    require(module.analyze(changed)["research"][0]["best_supplied_social"] == ["1"],
            "candidate label is not continuous optimum")
    require(sha256(INPUT.read_bytes()).hexdigest() == original_hash, "input preserved")
    checks.append(f"Executable: quiet import, exact preserved output, arbitrary-CWD default, candidate-limited labels, direct-channel sensitivity and {len(invalid)} invalid cases rejected by API and CLI")

    html = (ROOT / "content/chapters/v06-c03.html").read_text()
    structure = Structure()
    structure.feed(html)
    require(structure.worked >= 2 and structure.exercises == structure.solutions == 8 and not structure.forbidden,
            "chapter fragment structure")
    require("Teach-back" in html and "Delayed-check answers" in html and "v06-c02.html" in html,
            "instruction and prerequisite")
    for name in structure.downloads:
        require(name.startswith("v06-c03-") and "/" not in name and (PROJECT / name).is_file(),
                "flat local download")
    require(len(structure.downloads) == 4, "lab download inventory")
    sources = json.loads((ROOT / "content/reviews/v06-c03-sources.json").read_text())
    require({s["id"] for s in sources} == structure.sources and len(sources) == 3, "source coverage")
    for source in sources:
        require(all(source.get(k) for k in ("id", "title", "url", "use", "checked", "verification")),
                "scoped source fields")
    checks.append("Structure: four worked cases, eight aligned full solutions, answered retention, four existing flat downloads and three scoped inspected primary sources")
    report = {"status": "passed", "checks": checks, "invalid_cases": len(invalid),
              "input_sha256": original_hash,
              "limitations": [
                  "Author numerical/structural audit, not independent human validation or empirical model evidence.",
                  "Finite grid spot checks complement the manuscript's exact concavity and contraction proofs; they do not replace continuous-domain arguments.",
                  "The downloadable research program compares supplied candidates; general continuous optimization is proved in prose, not implemented as a numerical optimizer.",
                  "Historical paper inspection is scoped; no historical dataset or coefficient is independently replicated.",
                  "Root owns prerequisite acceptance, integration and publication; visual/mobile/print UI QA remains pending."
              ]}
    json.dumps(report)
    return report


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False))

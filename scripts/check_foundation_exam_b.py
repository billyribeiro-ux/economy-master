#!/usr/bin/env python3
"""Read-only, standard-library checks for the original foundation Form B."""
from fractions import Fraction as F
from html.parser import HTMLParser
from itertools import combinations, permutations, product
import json
import math
from pathlib import Path
import re
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "content/assessment-parts/foundation-form-b.html"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


class Form(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.headings = []
        self.links = []
        self.tables = {}
        self.table = None
        self.row = None
        self.cell = None
        self.text = []
        self.depth = 0
        self.part_depth = None
        self.parts = []
        self.solution_depth = None
        self.solutions = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag in ("h1", "h2", "h3"):
            self.headings.append((tag, attrs.get("id")))
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "table":
            self.table = attrs.get("id")
            self.tables[self.table] = []
        if tag == "tr" and self.table:
            self.row = []
        if tag == "td" and self.table:
            self.cell = []
        if tag == "ol":
            self.depth += 1
            if attrs.get("class") == "exam-parts":
                self.part_depth = self.depth
                self.parts.append(0)
            elif attrs.get("class") == "exam-solutions":
                self.solution_depth = self.depth
        if tag == "li":
            if self.depth == self.part_depth:
                self.parts[-1] += 1
            if self.depth == self.solution_depth:
                self.solutions += 1

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            if self.row:
                self.tables[self.table].append(self.row)
            self.row = None
        if tag == "table":
            self.table = None
        if tag == "ol":
            if self.depth == self.part_depth:
                self.part_depth = None
            if self.depth == self.solution_depth:
                self.solution_depth = None
            self.depth -= 1

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def mean(values):
    return sum(map(F, values), F(0)) / len(values)


def variance(values):
    center = mean(values)
    return mean([(F(value)-center)**2 for value in values])


def check():
    html = MANUSCRIPT.read_text(encoding="utf-8")
    doc = Form()
    doc.feed(html)
    text = "".join(doc.text)
    require(doc.headings == [("h2", "form-b")], "form-b h2 without h1")
    require(len(doc.ids) == len(set(doc.ids)), "unique anchors")
    require(all(x == "form-b" or x.startswith("foundation-b-") for x in doc.ids), "namespaced anchors")
    require(all(f"foundation-b-q{i}" in doc.ids for i in range(1,5)), "four domains")
    require(doc.parts == [5]*4 and doc.solutions == 4, "four matching five-part domains")
    require(html.count("<strong>(5)</strong>") == 20 and text.count("Scoring:") == 20,
            "twenty five-point prompts and allocations")
    require(all(term in text for term in ["180 minutes", "closed notes", "nonprogrammable", "85/100", "19/25", "synthetic"]),
            "exam scope and rules")
    require(len(doc.links) == 17 and all((ROOT/"content/chapters"/link).is_file() for link in doc.links),
            "seventeen accepted-method routes exist")

    # D1: read the original tables and post double-entry changes one at a time.
    opening = {row[0]: F(row[1]) for row in doc.tables["foundation-b-opening"]}
    transactions = {row[0]: [int(x) for x in re.findall(r"\d+", row[1])]
                    for row in doc.tables["foundation-b-transactions"]}
    revenue, cogs, cash_sale = transactions["Sale"]
    collection, = transactions["Old receivable collected"]
    purchase, purchase_cash = transactions["Inventory purchased"]
    supplier_payment, = transactions["Supplier payment"]
    wages, = transactions["Wages"]
    depreciation, = transactions["Depreciation"]
    principal, = transactions["Bank principal payment"]
    interest, = transactions["Interest"]
    distribution, = transactions["Owner distribution"]
    def identity(state):
        assets = sum(state[k] for k in ["Cash","Receivables","Inventory","Equipment, net"])
        claims = sum(state[k] for k in ["Supplier payables","Bank principal owed","Equity"])
        return assets, claims
    require(identity(opening) == (1000,1000), "opening identity")
    entries = [
        {"Cash":cash_sale,"Receivables":revenue-cash_sale,"Inventory":-cogs,"Equity":revenue-cogs},
        {"Cash":collection,"Receivables":-collection},
        {"Cash":-purchase_cash,"Inventory":purchase,"Supplier payables":purchase-purchase_cash},
        {"Cash":-supplier_payment,"Supplier payables":-supplier_payment},
        {"Cash":-wages,"Equity":-wages},
        {"Equipment, net":-depreciation,"Equity":-depreciation},
        {"Cash":-principal,"Bank principal owed":-principal},
        {"Cash":-interest,"Equity":-interest},
        {"Cash":-distribution,"Equity":-distribution}
    ]
    closing = opening.copy()
    for entry in entries:
        for key,delta in entry.items():
            closing[key] += delta
        assets,claims = identity(closing)
        require(assets == claims, "identity after each journal entry")
    expected = {"Cash":140,"Receivables":140,"Inventory":220,"Equipment, net":480,
                "Supplier payables":130,"Bank principal owed":260,"Equity":590}
    require(closing == expected and identity(closing) == (980,980), "seven closing stocks")
    profit = revenue-cogs-wages-depreciation-interest
    require(profit == 4 and closing["Equity"]-opening["Equity"]+distribution == profit,
            "profit independently reconciles retained earnings")
    operating = cash_sale+collection-purchase_cash-supplier_payment-wages-interest
    bridge = profit+depreciation-(closing["Receivables"]-opening["Receivables"])-(closing["Inventory"]-opening["Inventory"])+(closing["Supplier payables"]-opening["Supplier payables"])
    financing = -principal-distribution
    require(operating == bridge == -6 and financing == -54, "cash versus accrual bridge")
    require(operating+financing == closing["Cash"]-opening["Cash"] == -60, "cash movement")
    monthly = F(24,100)/12
    bank_quarter = (1+monthly)**3-1
    bank_repayment = 900*(1+monthly)**3
    annual = (1+monthly)**12-1
    internal = 900*F(105,100)
    require(F(1000,900)-1 == F(1,9) and monthly == F(1,50), "financing denominators")
    require(bank_quarter == F(7651,125000) and bank_repayment == F(1193859,1250), "bank quarterly quote")
    require(math.isclose(float(annual)*100,26.824179456254536,abs_tol=1e-12), "bank effective annual rate")
    require(internal == 945 < bank_repayment < 1000, "equivalent future-cost ordering")
    require(F(900) < bank_repayment/F(105,100) < F(1000)/F(105,100), "same ranking after common-date discount")

    # D2: independent active-set candidates on all edges, plus square identities.
    def loss(x,y):
        return (x-4)**2 + 2*(y-3)**2
    def edge_optimum(b):
        candidates = [(F(0),F(0)), (F(0),min(F(3),b)), (min(F(4),b),F(0))]
        on_resource = (F(2*b-2,3),F(b+2,3))
        if all(z>=0 for z in on_resource):
            candidates.append(on_resource)
        if b>=7:
            candidates.append((F(4),F(3)))
        feasible = [(x,y) for x,y in candidates if x>=0 and y>=0 and x+y<=b]
        return min(feasible,key=lambda xy:loss(*xy))
    require(edge_optimum(F(4)) == (2,2) and loss(2,2) == 6, "edge minimizers recover certificate")
    require(2*(2-4)+4 == 0 and 4*(2-3)+4 == 0, "KKT stationarity")
    for x,y in product([F(i,2) for i in range(17)],repeat=2):
        lagrangian = loss(x,y)+4*(x+y-4)
        require(lagrangian == (x-2)**2+2*(y-2)**2+6 >= 6, "dual square completion over retained domain")
        if x+y<=4:
            require(loss(x,y) >= lagrangian >= 6, "weak duality feasible lower bound")
    require(loss(1,3)-6 == 3, "suboptimal candidate gap")
    require(edge_optimum(F(0)) == (0,0) and loss(0,0) == 34, "capacity zero boundary")
    require(edge_optimum(F(8)) == (4,3) and loss(4,3) == 0, "inactive capacity boundary")
    for b in [F(i,2) for i in range(21)]:
        optimum = edge_optimum(b)
        require(loss(*optimum) >= 22-4*b, "fixed-multiplier lower bound at changed capacity")
    capacity = F(0)
    paths = []
    for t in range(9):
        require(capacity == 4*(1-F(1,2)**t) and capacity>=0, "capacity recurrence closed form/domain")
        paths.append(capacity)
        capacity = 2+capacity/2
    require(next(t for t,b in enumerate(paths) if abs(b-4)<=F(1,8)) == 5, "first tolerance date")
    for initial in [F(0),F(1),F(4),F(10)]:
        capacity = initial
        for t in range(7):
            require(capacity>=0 and abs(capacity-4)==abs(initial-4)*F(1,2)**t, "global admissible deviation stability")
            capacity=2+capacity/2

    # D3: enumerate both ordered and unordered design laws, never use iid SE.
    population = [F(0),F(2),F(5),F(9)]
    pairs = list(combinations(population,2))
    pair_means = [mean(pair) for pair in pairs]
    require(pair_means == [F(1),F(5,2),F(9,2),F(7,2),F(11,2),F(7)], "six unordered means")
    require(mean(pair_means) == mean(population) == 4 and variance(pair_means) == F(23,6), "finite-population unbiasedness and variance")
    ordered = list(permutations(population,2))
    covariance = mean([(x-4)*(y-4) for x,y in ordered])
    require(variance(population)==F(23,2) and covariance==F(-23,6), "ordered-draw moments")
    require((2*variance(population)+2*covariance)/4==variance(pair_means), "covariance reconstruction")
    independent_means=[mean(pair) for pair in product(population,repeat=2)]
    require(variance(independent_means)==F(23,4), "replacement enumeration")
    null_tail=lambda observed:F(sum(m>=observed for m in pair_means),len(pair_means))
    pvalue=null_tail(F(7))
    require(pvalue==F(1,6) and pvalue<=F(1,5) and pvalue>F(1,20), "exact test decisions")
    require(F(sum(null_tail(m)<=F(1,5) for m in pair_means),6)==F(1,6), "actual discrete test size")
    wealth=[9,25];eu=mean([math.isqrt(w) for w in wealth]);ce=eu**2
    require(mean(wealth)==17 and eu==4 and ce==16 and mean(wealth)-ce==1, "exact square-root utility decision")
    stopped=[];hindsight=[]
    for first,second in product([1,-1],repeat=2):
        at_one=first;at_two=first+second
        stopped.append(at_one if first==1 else at_two)
        hindsight.append(max(at_one,at_two))
    require(stopped==[1,1,0,-2] and mean(stopped)==0, "bounded stopping enumeration")
    require(hindsight==[2,1,0,-1] and mean(hindsight)==F(1,2), "hindsight-selection expectation")
    for first in [1,-1]:
        require(mean([first-1,first+1])==first, "conditional fairness")
        hindsight_stops_at_one=[first>=first+second for second in [-1,1]]
        require(hindsight_stops_at_one==[True,False], "hindsight event depends on unavailable second sign")

    # D4: actual HTML data, SQL multiplicity and exact group reweighting.
    records=[(row[0],row[1],int(row[2]),row[3].split(',')) for row in doc.tables['foundation-b-firms']]
    values=[row[2] for row in records]
    small=mean([row[2] for row in records if row[1]=='small'])
    large=mean([row[2] for row in records if row[1]=='large'])
    require(mean(values)==F(9,2) and small==2 and large==12, "original group means")
    require(F(1,4)*small+F(3,4)*large==F(19,2), "proposed target weights")
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE firm(id TEXT PRIMARY KEY, grp TEXT, fee INT)')
        db.execute('CREATE TABLE directory(id TEXT, tag TEXT, PRIMARY KEY(id,tag))')
        db.executemany('INSERT INTO firm VALUES(?,?,?)',[(i,g,v) for i,g,v,t in records])
        db.executemany('INSERT INTO directory VALUES(?,?)',[(i,tag) for i,g,v,tags in records for tag in tags])
        joined=db.execute('SELECT COUNT(*),SUM(fee) FROM firm JOIN directory USING(id)').fetchone()
        group_totals=db.execute('SELECT grp,COUNT(*),SUM(fee) FROM firm JOIN directory USING(id) GROUP BY grp').fetchall()
        preserved=db.execute('SELECT COUNT(*),SUM(fee) FROM firm WHERE EXISTS(SELECT 1 FROM directory WHERE directory.id=firm.id)').fetchone()
    require(joined==(7,42) and F(joined[1],joined[0])==6 and preserved==(4,18), "tag join and existence repair")
    joined_means={group:F(total,count) for group,count,total in group_totals}
    require(joined_means=={'large':12,'small':F(3,2)}, "within-group multiplicity bias")
    require(F(1,4)*joined_means['small']+F(3,4)*joined_means['large']==F(75,8), "group reweighting does not undo within-group duplication")
    bins=[(0,3),(3,6),(6,15)]
    counts=[sum(lo<=value<hi or (i==2 and value==hi) for value in values) for i,(lo,hi) in enumerate(bins)]
    heights=[F(count,len(values)*(hi-lo)) for count,(lo,hi) in zip(counts,bins)]
    areas=[height*(hi-lo) for height,(lo,hi) in zip(heights,bins)]
    require(counts==[2,1,1] and heights==[F(1,6),F(1,12),F(1,36)] and areas==[F(1,2),F(1,4),F(1,4)], "histogram density units and area")
    require(sum(areas)==1 and F(sum(row[1]=='small' for row in records),len(records))==F(3,4), "sample histogram weighting")
    require(sys.float_info.radix==2 and sys.float_info.mant_dig==53, "declared binary64 significand environment")
    ledger=[2**53+3,-(2**53+2)]
    represented=[F.from_float(float(x)) for x in ledger]
    exact_original=sum(ledger);exact_stored=sum(represented)
    require(exact_original==1 and represented==[2**53+4,-(2**53+2)] and exact_stored==2,
            "representation probe values")
    require(F.from_float(math.fsum(map(float,ledger)))==exact_stored and exact_stored-exact_original==1,
            "conversion error versus exact stored-value accumulation")
    model_a=lambda u,d:50-4*d
    model_b=lambda u,d:50-10*u+6*d
    observed_a=[(u,model_a(u,u)) for u in [0,1]]
    observed_b=[(u,model_b(u,u)) for u in [0,1]]
    require(observed_a==observed_b==[(0,50),(1,46)], "observationally equivalent structural models")
    require(mean([model_a(u,1)-model_a(u,0) for u in [0,1]])==-4
            and mean([model_b(u,1)-model_b(u,0) for u in [0,1]])==6, "opposite causal effects")
    require(all(y==50-4*d for d,y in observed_a), "same predictive law")

    required_answers=['4 USD','980 USD','−6 USD','−54 USD','955.0872 USD','26.82418%',
                      '945 USD','x=2,y=2,λ=4','6 squared activity units','V(b)≥22−4b',
                      'V(0)=34','V(8)=0','t=5','23/6 USD²','23/4 USD²','1/6≈0.166667',
                      'CE=16 USD','1,1,0,−2 USD','2,1,0,−1 USD','19/2=9.5 USD',
                      '75/8=9.375 USD','(1/6,1/12,1/36) per USD','−4 USD','+6 USD']
    require(all(answer in text for answer in required_answers), "computed answers appear in full solutions")
    return {
        'assessment':'foundation-form-b','status':'passed',
        'checks':[
            'Four25-point domains; twenty5-point parts and explicit allocations; unique foundation-b IDs; complete solution groups;17 existing chapter routes',
            'HTML-input double-entry journal checks after all9 events; all7 closing stocks; income/equity and independent direct/indirect cash bridges; exact financing rates and present/future cost rankings',
            'Independent edge minimization, KKT residuals,289 Lagrangian square-completion cases,21 capacity sensitivity cases and zero/slack boundaries; exact stable recurrence and first-tolerance date',
            'All6 unordered samples,12 ordered samples and16 replacement samples; finite-population mean/covariance/variance; exact upper-tail p-values and actual rejection probability',
            'Square-root utility mean/CE/risk premium; all4 bounded-stopping and hindsight paths with conditional-fairness and nonadapted selection checks',
            'HTML-input group means and SQL tag join; within-group reweighting defect and grain-preserving existence check; unequal-bin histogram density and areas',
            'Integer versus represented binary64 ledger references and fsum conversion limitation; two structural models with identical observations/predictions and opposite causal effects'
        ],
        'limitations':[
            'Mathematical derivations, economic contracts, sampling interpretations and scoring were also manually reviewed; finite checks do not replace that review.',
            'The floating representation probe requires the explicitly declared binary64 significand environment. Exact arithmetic checks otherwise use rational/integer references.',
            'All scenarios are synthetic and do not establish real-world economic, sampling, predictive or causal validity.',
            'Assessment timing and score thresholds are design choices, not empirically calibrated or university-certified standards. No visual/mobile/print QA was performed.',
            'Root retains final cross-volume assembly, independent review and acceptance.'
        ]
    }


if __name__ == '__main__':
    print(json.dumps(check(),indent=2,ensure_ascii=False))

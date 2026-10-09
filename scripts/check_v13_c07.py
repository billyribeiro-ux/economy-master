"""Quiet, bounded exact checks for the four-file V13-C07 author package.

Finite tree and stationary-policy reconstruction supports separately audited general
proofs. Successful import, check(root=None), and no-argument CLI write nothing.
"""
from __future__ import annotations
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path
import sys

FILES = ('content/chapters/v13-c07.html','scripts/check_v13_c07.py',
         'content/reviews/v13-c07-sources.json','content/reviews/v13-c07-author.json')
SOURCES = {'v13-c06-manea-noncoop2017','v13-c06-yildiz-games2022'}
ROUTES = {'v13-c0'+str(i)+'.html' for i in (3,4,5,6,8)}
PD = (((4,4),(-1,6)),((6,-1),(1,1)))
LOTTERY = (((2,2),(0,5)),((5,0),(1,1)))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    need(type(x) in (int,float,F), 'number excludes bool/string/complex')
    if type(x) is float:
        need(math.isfinite(x), 'finite number')
        x=F(str(x))
    else:
        x=F(x)
    need(abs(x)<=10**6 and x.denominator<=10**9, 'bounded rational domain')
    return x


def probability(x):
    x=number(x)
    need(0<=x<=1, 'probability interval')
    return x


def discount(x):
    x=number(x)
    need(0<x<1, 'strict discounted domain')
    return x


def vector(xs, n=None, limit=8):
    need(type(xs) in (list,tuple) and 1<=len(xs)<=limit, 'bounded vector')
    need(n is None or len(xs)==n, 'vector dimension')
    return tuple(number(x) for x in xs)


def simplex(xs, n=None):
    xs=vector(xs,n)
    need(all(x>=0 for x in xs) and sum(xs)==1, 'probability simplex')
    return xs


def bayes(weights):
    weights=vector(weights)
    need(all(x>=0 for x in weights) and sum(weights)>0, 'positive conditioning mass')
    return tuple(x/sum(weights) for x in weights)


def stage_game(table):
    need(type(table) in (list,tuple) and len(table)==2, 'two-action rows')
    result=[]
    for row in table:
        need(type(row) in (list,tuple) and len(row)==2, 'two-action columns')
        result.append(tuple(vector(cell,2) for cell in row))
    return tuple(result)


def nash(table, p, q):
    game=stage_game(table);p=probability(p);q=probability(q)
    mixes=((p,1-p),(q,1-q))
    for i in range(2):
        values=[]
        for action in range(2):
            values.append(sum(mixes[1-i][other]*game[action if i==0 else other]
                              [other if i==0 else action][i] for other in range(2)))
        if any(mass>0 and values[a]<max(values) for a,mass in enumerate(mixes[i])):
            return False
    return True


def plan_law(rows):
    need(type(rows) in (list,tuple) and 1<=len(rows)<=8, 'bounded pure-plan support')
    out={}
    for row in rows:
        need(type(row) in (list,tuple) and len(row)==2, 'plan/mass pair')
        plan,mass=row
        need(type(plan) in (list,tuple) and len(plan)==3 and
             all(type(a) is int and a in (0,1) for a in plan), 'binary three-coordinate plan')
        plan=tuple(plan)
        need(plan not in out, 'unique plan support')
        out[plan]=probability(mass)
    need(sum(out.values())==1, 'complete plan probability')
    return out


def behavioral_from_plans(rows):
    law=plan_law(rows)
    first=sum(m for (a,b,c),m in law.items() if a==0)
    at_x=sum(m for (a,b,c),m in law.items() if a==0 and b==0)/first if first else F(1,2)
    at_y=sum(m for (a,b,c),m in law.items() if a==1 and c==0)/(1-first) if first<1 else F(1,2)
    return first,at_x,at_y


def terminal_from_plans(rows):
    law=plan_law(rows);out=[F(0)]*4
    for (a,b,c),mass in law.items():
        out[2*a+(b if a==0 else c)]+=mass
    return tuple(out)


def terminal_from_behavior(b):
    x,lx,ly=(probability(z) for z in vector(b,3))
    return x*lx,x*(1-lx),(1-x)*ly,(1-x)*(1-ly)


def solve_linear(a,b):
    n=len(b)
    need(1<=n<=5 and len(a)==n and all(len(row)==n for row in a), 'bounded square system')
    aug=[list(map(F,row))+[F(rhs)] for row,rhs in zip(a,b)]
    for j in range(n):
        pivot=next((i for i in range(j,n) if aug[i][j]),None)
        need(pivot is not None, 'nonsingular system')
        aug[j],aug[pivot]=aug[pivot],aug[j]
        scale=aug[j][j];aug[j]=[x/scale for x in aug[j]]
        for i in range(n):
            if i!=j:
                scale=aug[i][j]
                aug[i]=[x-scale*y for x,y in zip(aug[i],aug[j])]
    return tuple(row[-1] for row in aug)


def markov_value(rewards, transitions, d):
    r=vector(rewards,limit=5);d=discount(d)
    need(type(transitions) in (list,tuple) and len(transitions)==len(r), 'transition rows')
    q=tuple(simplex(row,len(r)) for row in transitions)
    a=tuple(tuple(F(i==j)-d*q[i][j] for j in range(len(r))) for i in range(len(r)))
    return solve_linear(a,r)


def punishment_policy(policy,d,grim=False):
    need(type(policy) in (tuple,list) and 2<=len(policy)<=5 and
         all(type(x) is int and x in (0,1) for x in policy), 'bounded binary automaton policy')
    if grim:
        need(len(policy)==2, 'grim has two states')
    T=len(policy)-1;rewards=[];transition=[]
    for state,action in enumerate(policy):
        opponent=0 if state==0 else 1
        rewards.append(PD[action][opponent][0])
        if state==0:
            nxt=0 if action==0 else T
        elif grim:
            nxt=1
        else:
            nxt=state-1 if action==1 else T
        transition.append(tuple(F(j==nxt) for j in range(T+1)))
    return markov_value(rewards,transition,d)


def lottery_values(lam,d,player,policy):
    lam=probability(lam);d=discount(d)
    need(type(player) is int and player in (0,1), 'player index')
    need(type(policy) in (list,tuple) and len(policy)==3 and
         all(type(x) is int and x in (0,1) for x in policy), 'two recommendations and punishment action')
    profiles=((0,1),(1,0));weights=(lam,1-lam)
    current=F(0);continue_prob=F(0)
    for k,(a,prob) in enumerate(zip(profiles,weights)):
        changed=list(a);changed[player]=policy[k]
        current+=prob*LOTTERY[changed[0]][changed[1]][player]
        continue_prob+=prob*F(policy[k]==a[player])
    punished=[1,1];punished[player]=policy[2]
    r=LOTTERY[punished[0]][punished[1]][player]
    return markov_value((current,r),((continue_prob,1-continue_prob),(0,1)),d)


def reputation_tree(prior,q,entry,entry2,fight2,d):
    """Enumerate dated terminal paths; C has only F, independent of R's controls."""
    prior=probability(prior);q=probability(q);entry=probability(entry);d=discount(d)
    e=tuple(probability(x) for x in vector(entry2,3))
    f=tuple(probability(x) for x in vector(fight2,3))
    histories=('O','F','A');stage={'O':(4,0),'F':(-1,-2),'A':(1,2)}
    incumbent=[F(0),F(0)];entrant1=F(0);joint={h:[F(0),F(0)] for h in histories}
    leaf_count=0
    for type_index,type_mass in enumerate((prior,1-prior)):
        first_fight=F(1) if type_index==0 else q
        paths=(('O',1-entry),('F',entry*first_fight),('A',entry*(1-first_fight)))
        for h,mass in paths:
            if not mass:
                continue
            k=histories.index(h)
            joint[h][type_index]+=type_mass*mass
            entrant1+=type_mass*mass*stage[h][1]
            rf=F(1) if type_index==0 else f[k]
            later=(('O',1-e[k]),('F',e[k]*rf),('A',e[k]*(1-rf)))
            for h2,mass2 in later:
                if mass2:
                    incumbent[type_index]+=mass*mass2*(stage[h][0]+d*stage[h2][0])
                    leaf_count+=1
    beliefs={h:bayes(mass)[0] if sum(mass) else None for h,mass in joint.items()}
    return {'incumbent_C_R':tuple(incumbent),'entrant1':entrant1,'beliefs':beliefs,
            'joint':joint,'leaves':leaf_count}


def unique_pairs(pairs):
    out={}
    for k,v in pairs:
        need(k not in out,'duplicate JSON key');out[k]=v
    return out


def reject_constant(value):
    raise ValueError('nonfinite JSON '+value)


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)


def fmt(x):
    return '('+','.join(fmt(y) for y in x)+')' if isinstance(x,(tuple,list)) else str(x)


class Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[];self.sources=[];self.links=[];self.worked=[];self.prompts=[];self.solutions=[]
        self.stack=[];self.anchors={};self.capture=self.exercises=self.answers=None
    def handle_starttag(self,tag,attrs):
        d=dict(attrs);classes=d.get('class','').split()
        if 'id' in d:self.ids.append(d['id'])
        if 'data-source' in d:self.sources.append(d['data-source'])
        if 'href' in d:self.links.append(d['href'])
        if tag=='article' and 'worked' in classes:self.worked.append(d.get('id'))
        if tag=='ol' and 'exercises' in classes:self.exercises=len(self.stack)
        if tag=='details' and 'solutions' in classes:self.answers=len(self.stack)
        if tag=='li' and self.exercises is not None:self.prompts.append(d.get('id'))
        if 'data-solution-for' in d:
            need(self.answers is not None,'answer outside standard disclosure');self.solutions.append(d['data-solution-for'])
        if 'data-calc' in d:
            need(self.capture is None and d['data-calc'] not in self.anchors,'unique numeric anchor')
            self.capture=d['data-calc'];self.anchors[self.capture]=''
        if tag not in {'br','hr','img','meta','link','input'}:self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag=='span' and self.capture is not None:self.capture=None
        need(bool(self.stack) and self.stack[-1]==tag,'balanced HTML '+tag);self.stack.pop()
        if tag=='ol' and self.exercises==len(self.stack):self.exercises=None
        if tag=='details' and self.answers==len(self.stack):self.answers=None
    def handle_data(self,data):
        if self.capture is not None:self.anchors[self.capture]+=data


def check(root=None):
    root=Path(root).resolve() if root is not None else Path(__file__).resolve().parent.parent
    paths=tuple(root/name for name in FILES);before=tuple(p.read_bytes() for p in paths)
    counts={'comparisons':0,'rejections':0,'stationary_policies':0,'reputation_terminal_paths':0}
    def eq(a,b,label):
        counts['comparisons']+=1;need(a==b,label+': '+repr(a)+' != '+repr(b))
    def yes(ok,label):
        counts['comparisons']+=1;need(ok,label)
    def rejects(call,label):
        try:call()
        except (ValueError,TypeError):counts['rejections']+=1
        else:raise ValueError('invalid domain accepted: '+label)
    reader=Reader();reader.feed(before[0].decode('utf-8'));reader.close()
    yes(not reader.stack,'balanced fragment')
    eq(len(reader.ids),len(set(reader.ids)),'unique IDs')
    eq(reader.worked,['v13-c07-case'+str(i) for i in range(1,7)],'six cases')
    prompts=['v13-c07-ex'+str(i) for i in range(1,13)]
    eq(reader.prompts,prompts,'twelve prompts');eq(reader.solutions,prompts,'twelve complete answers')
    eq(set(reader.sources),SOURCES,'exact reused source IDs')
    eq({x for x in reader.links if not x.startswith('https://')},ROUTES,'flat syntax, no runtime chapter dependencies')
    sources,author=load_json(paths[2]),load_json(paths[3])
    eq({x['id'] for x in sources['proposals']},SOURCES,'two scoped source proposals')
    for source in sources['proposals']:
        eq(source['inspection']['actual_inspector'],'ito_author','actual added-scope inspector')
        yes(bool(source['limits']),'source limits retained')
    bindings={b['path']:b for b in author['bindings']}
    eq(set(bindings),set(FILES[:3]),'three nonself runtime bindings')
    for name,raw in zip(FILES[:3],before[:3]):
        eq((bindings[name]['bytes'],bindings[name]['sha256']),(len(raw),sha256(raw).hexdigest()),'bound '+name)
    eq([x['id'] for x in author['exercise_audit']],prompts,'every exact prompt audited')
    eq(author['open_findings'],[],'no open author finding')
    anchors={}

    # Mixed-plan path enumeration versus independent conditional/product construction.
    mixture=(((0,0,0),F(1,2)),((0,1,0),F(1,6)),((1,0,1),F(1,3)))
    b=behavioral_from_plans(mixture)
    eq(b,(F(2,3),F(3,4),0),'remembered-prefix behavior')
    terminal=terminal_from_plans(mixture)
    eq(terminal,terminal_from_behavior(b),'Kuhn realization, direct plan masses')
    independent=[]
    for plan in product((0,1),repeat=3):
        mass=F(1)
        for a,p in zip(plan,b):mass*=p if a==0 else 1-p
        independent.append((plan,mass))
    eq(terminal_from_plans(independent),terminal,'product plan realization')
    yes(dict(mixture)!=dict(independent),'unused plan correlations differ')
    for unreachable in (F(0),F(1,3),F(1)):
        eq(terminal_from_behavior((1,F(1,4),unreachable)),(F(1,4),F(3,4),0,0),'zero-prefix arbitrariness')
    eq(behavioral_from_plans((((0,0,0),1),)),(1,1,F(1,2)),'defined arbitrary zero-prefix choice')
    anchors['kuhn-terminal-law']=fmt(terminal)

    # W1: primitive leaf game and support best replies, including all face boundaries.
    entry_game=(((2,3),(2,3)),((-1,-2),(4,1)))
    cutoff=F(4-2,4-(-1));anchors['entry-threat-cutoff']=fmt(cutoff)
    eq(cutoff,F(2,5),'entry indifference')
    pure_ne=[]
    for out,fight in product((0,1),repeat=2):
        if nash(entry_game,out,fight):pure_ne.append((out,fight))
    eq(pure_ne,[(0,0),(1,1)],'all pure normal-form equilibria')
    for x,f in ((0,F(1,5)),(0,F(2,5)),(0,F(3,5)),(0,1),(F(1,2),F(2,5)),(F(1,2),0),(1,0)):
        expected=(x==1 and f==0) or (x==0 and f>=cutoff)
        eq(nash(entry_game,1-x,f),expected,'complete face characterization witness')
    for k,sign in ((1,1),(2,0),(3,-1)):
        difference=entry_game[1][1][0]-k-entry_game[0][1][0]
        eq((difference>0)-(difference<0),sign,'SPE entry cost boundary')
        yes(entry_game[1][1][1]>entry_game[1][0][1],'off-path accommodation unchanged')

    # W2 plus the own-factor lemma: ratios built from actual path probabilities.
    prior=(F(1,3),F(2,3));a_value=prior[0]*3;b_value=prior[1]*2
    anchors['weak-belief-cutoff']=fmt(F(2,5));anchors['state-action-values']=fmt((a_value,b_value))
    eq((a_value,b_value),(1,F(4,3)),'Bayesian action values')
    for theta in (F(1,3),F(2,5),F(3,4)):
        eq(3*theta>=2*(1-theta),theta>=F(2,5),'weak-PBE belief inequality')
    for epsilon in (F(1,2),F(1,8),F(1,128)):
        eq(bayes(tuple(epsilon*p for p in prior)),prior,'off-path Continue factor cancels')
        eq(bayes(tuple((1-epsilon)*p for p in prior)),prior,'surviving sequential tremble')
    likelihood=(F(3,4),F(1,4))
    conditional=bayes(tuple(p*l for p,l in zip(prior,likelihood)))
    eq(conditional,(F(3,5),F(2,5)),'remembered-Go posterior')
    for g in (F(1,2),F(1,16),F(1,1024),F(1)):
        masses=tuple(p*g*l for p,l in zip(prior,likelihood))
        eq(sum(masses),5*g/12,'conditional-reach denominator')
        eq(bayes(masses),conditional,'own changed probability cancels')
    anchors['own-factor-posterior']=fmt(conditional[0])
    # Agent payoff difference = positive reach times conditional gain before its limit.
    for reach in (F(1,2),F(1,10),F(1,1000)):
        payoff_A=(1-reach)*7+reach*a_value
        payoff_B=(1-reach)*7+reach*b_value
        eq(payoff_B-payoff_A,reach*(b_value-a_value),'agent reach times conditional difference')
        yes((payoff_B-payoff_A)/reach>0,'positive division retains conditional incentive')

    # W3–W4: exact linear systems for complete stationary policies, no geometric oracle.
    for own in range(2):
        for other in range(2):
            gain=(PD[1][other][own]-PD[0][other][own] if own==0 else
                  PD[other][1][own]-PD[other][0][own])
            eq(gain,2,'both players strict stage dominance')
    anchors['grim-cutoff']=fmt(F(6-4,6-1))
    for d in (F(1,3),F(2,5),F(3,4)):
        prescribed=punishment_policy((0,1),d,grim=True)
        eq(prescribed,(4/(1-d),1/(1-d)),'grim linear-system values')
        candidates=[punishment_policy(policy,d,grim=True) for policy in product((0,1),repeat=2)]
        counts['stationary_policies']+=len(candidates)
        best=tuple(max(row[s] for row in candidates) for s in range(2))
        eq(best==prescribed,d>=F(2,5),'grim complete policy test')
        eq(6+d*prescribed[1]-prescribed[0],(2-5*d)/(1-d),'grim deviation surplus')
    for T,d in ((1,F(1,2)),(2,F(1,2)),(2,F(1,3)),(2,F(3,4)),(3,F(2,5))):
        policy=(0,)+(1,)*T
        values=punishment_policy(policy,d)
        closed=(4/(1-d),)+tuple(sum(d**j for j in range(k))+d**k*4/(1-d) for k in range(1,T+1))
        eq(values,closed,'forgiveness transition solve versus finite sums')
        current_gap=values[0]-(6+d*values[T])
        eq(current_gap,3*sum(d**t for t in range(1,T+1))-2,'cooperation IC identity')
        for k in range(1,T+1):
            gap=values[k]-(-1+d*values[T])
            eq(gap,2+d*(values[k-1]-values[T]),'reset punishment incentive')
            yes(gap>=2,'credible punishment at every state')
        candidates=[punishment_policy(p,d) for p in product((0,1),repeat=T+1)]
        counts['stationary_policies']+=len(candidates)
        best=tuple(max(row[s] for row in candidates) for s in range(T+1))
        eq(best==values,current_gap>=0,'all stationary policy oracle for automaton')
        if T==2 and d==F(1,2):
            anchors['forgiveness-values']=fmt(values)
            anchors['forgiveness-coop-deviation']=fmt(6+d*values[T])
            anchors['forgiveness-punishment-deviation']=fmt(-1+d*values[T])
        if T==1 and d==F(1,2):anchors['one-period-deviation']=fmt(6+d*values[T])
    eq(3*F(2,3),2,'one-period exact threshold')
    # The positive quadratic root is identified by its polynomial and an exact bracket.
    lo,hi=F(457,1000),F(458,1000)
    yes(3*lo*lo+3*lo-2<0<3*hi*hi+3*hi-2,'two-period root bracket')
    for T in (1,2,3):
        d=F(2,5)
        eq(3*sum(d**t for t in range(1,T+1)),2*(1-d**T),'finite/infinite boundary exact gap')
    # Uniform normalized tail, with a direct finite prefix plus closed residual.
    d=F(1,2);M=6;K=5
    eq((1-d)*sum(2*M*d**t for t in range(K,K+4))+2*M*d**(K+4),2*M*d**K,'tail bound identity')

    # W5: all two-signal/punishment policies versus conditional obedience margins.
    eq(nash(LOTTERY,0,0),True,'credible BB punishment')
    for t in (F(0),F(1,2),F(1)):
        eq(t*5+(1-t)*1,1+4*t,'individual security best reply')
    for lam,d in ((F(1,2),F(2,5)),(F(1,3),F(1,2)),(F(1,3),F(3,5)),
                  (F(2,5),F(1,2)),(F(3,5),F(1,2)),(F(1,5),F(3,4))):
        target=(5*(1-lam),5*lam);profiles=((0,1),(1,0));weights=(lam,1-lam)
        thresholds=tuple(1/v for v in target)
        all_pass=True
        for i in range(2):
            gains=[]
            for a in profiles:
                other=list(a);other[i]=1-a[i]
                gains.append(LOTTERY[other[0]][other[1]][i]-LOTTERY[a[0]][a[1]][i])
            eq(max(gains),1,'maximum temptation includes losing signal')
            margins=tuple(d*(target[i]-1)-(1-d)*gain for gain in gains)
            supported_pass=all(x>=0 for x in margins)
            eq(supported_pass,d>=thresholds[i],'exact signal-by-signal bound')
            policy=(profiles[0][i],profiles[1][i],1)
            value=lottery_values(lam,d,i,policy)
            eq(value,(target[i]/(1-d),1/(1-d)),'iid cooperative and Nash state values')
            candidates=[lottery_values(lam,d,i,p) for p in product((0,1),repeat=3)]
            counts['stationary_policies']+=len(candidates)
            best=tuple(max(row[s] for row in candidates) for s in range(2))
            eq(best==value,supported_pass,'complete recommendation policy oracle')
            all_pass &= supported_pass
        if lam==F(1,2):
            anchors['lottery-target']=fmt(target);anchors['lottery-cutoff']=fmt(max(thresholds))
        if lam==F(1,3):
            anchors['changed-lottery-target']=fmt(target);anchors['changed-lottery-bounds']=fmt(thresholds)
        if d==F(1,2):
            eq(all_pass,F(2,5)<=lam<=F(3,5),'half-discount exact lambda interval')
    anchors['half-discount-lottery-interval']='[2/5,3/5]'
    for lam in (F(1,10),F(9,10)):
        yes(min(5*lam,5*(1-lam))<1,'outside security interval impossible target')
    eq((5*(1-F(1,5)),5*F(1,5)),(4,1),'weak-security endpoint distinct from strict surplus')

    # W6: direct dated terminal path enumeration, off-path deviations and Bayes trembles.
    d=F(4,5);e=1-F(2,3)/d
    eq(e,F(1,6),'mix from incumbent indifference')
    for prior,expected_q,entry,expected_entry,expected_path in (
            (F(1,3),F(1,2),0,F(-2,3),(F(24,5),F(16,5))),
            (F(1,5),F(1,4),1,F(2,5),(F(9,5),F(23,15)))):
        q=prior/(1-prior);eq(q,expected_q,'Bayes-derived rational fight mix')
        expected_beliefs={'O':prior,'F':F(1,2),'A':F(0)}
        entries=(1,e,1)
        equilibrium=reputation_tree(prior,q,entry,entries,(0,0,0),d)
        counts['reputation_terminal_paths']+=equilibrium['leaves']
        path=tuple(reversed(equilibrium['incumbent_C_R']))
        eq(path,expected_path,'type-specific on-path utility ledger')
        hypothetical=reputation_tree(prior,q,1,entries,(0,0,0),d)
        counts['reputation_terminal_paths']+=hypothetical['leaves']
        eq(hypothetical['entrant1'],expected_entry,'first entrant hypothetical current payoff')
        eq(hypothetical['entrant1'],2-8*prior,'primitive entry formula')
        yes((entry==0 and expected_entry<0) or (entry==1 and expected_entry>0),'first-entry best reply')
        response=[]
        for forced_q in (1,0):
            forced=reputation_tree(prior,forced_q,1,entries,(0,0,0),d)
            counts['reputation_terminal_paths']+=forced['leaves']
            response.append(forced['incumbent_C_R'][1])
        eq(tuple(response),(F(9,5),F(9,5)),'full continuation R F/A indifference')
        for h,p in expected_beliefs.items():
            entry_pay=2*(1-p)-2*p
            if h=='F':eq(entry_pay,0,'post-F entrant mixes')
            else:yes(entry_pay>0,'post-O/A entrant strictly enters')
            eq(1-(-1),2,'last rational response strictly accommodates')
        for eps in (F(1,4),F(1,16),F(1,256)):
            trembled=reputation_tree(prior,q,eps if entry==0 else 1-eps,(1-eps,e,1-eps),(eps,eps,eps),d)
            counts['reputation_terminal_paths']+=trembled['leaves']
            eq(trembled['beliefs'],expected_beliefs,'one fully mixed sequence all public-history beliefs')
            yes(all(sum(m)>0 for m in trembled['joint'].values()),'every relevant public history reached')
        if prior==F(1,3):
            anchors['reputation-response-values']=fmt(tuple(response))
            anchors['reputation-first-entry']=fmt(expected_entry)
            anchors['reputation-rational-path']=fmt(path[0]);anchors['reputation-commitment-path']=fmt(path[1])
        else:
            anchors['reputation-changed-q']=fmt(q);anchors['reputation-changed-entry']=fmt(expected_entry)
            anchors['reputation-changed-path']=fmt(path)
    # Absentminded transfer: leaf probabilities and a global completed-square certificate.
    optimal=F(3,8);value=5*(1-optimal)*optimal+(1-optimal)**2
    eq(value,F(25,16),'absentminded leaf sum')
    for p in (F(0),optimal,F(1,2),F(1)):
        leaf=5*(1-p)*p+(1-p)**2
        eq(leaf,F(25,16)-4*(p-optimal)**2,'global concave quadratic certificate')
    yes(value>1,'behavior exceeds every mixed pure-plan average')
    anchors['absentminded-optimum']=fmt((optimal,value))

    # Explicit malformed domains. Economically unsuccessful valid plans above are not rejected.
    for bad in (True,'1',complex(1,0),float('nan'),float('inf'),10**7,F(1,10**10)):
        rejects(lambda bad=bad:number(bad),'invalid scalar')
    for bad in (-1,F(3,2),True):rejects(lambda bad=bad:probability(bad),'probability range')
    for bad in (0,1,-1,F(3,2)):rejects(lambda bad=bad:discount(bad),'discount domain')
    for bad in ([],[0,0],[-1,2],[1]*9):rejects(lambda bad=bad:bayes(bad),'conditional mass')
    for bad in ([],[[1]],[[[1,2],[1,2]]],[[[1,2],[1,2]],[[1],[1,2]]]):
        rejects(lambda bad=bad:stage_game(bad),'payoff dimensions')
    for bad in ([],[((0,0,0),F(1,2))],[((0,0,0),F(1,2)),((0,0,0),F(1,2))],
                [((0,True,0),1)],[((0,0),1)],[((0,0,2),1)]):
        rejects(lambda bad=bad:plan_law(bad),'complete finite plan law')
    for bad in ((0,), (0,1,1,1,1,1),(0,True),(0,2)):
        rejects(lambda bad=bad:punishment_policy(bad,F(1,2)),'punishment state/action bounds')
    rejects(lambda:markov_value((1,2),((1,0),),F(1,2)),'transition row dimension')
    rejects(lambda:markov_value((1,2),((1,1),(0,1)),F(1,2)),'transition simplex')
    rejects(lambda:markov_value((1,2),((1,),(0,1)),F(1,2)),'transition column dimension')
    rejects(lambda:lottery_values(F(-1,5),F(1,2),0,(0,1,1)),'invalid lottery probability')
    rejects(lambda:lottery_values(F(1,2),F(1,2),2,(0,1,1)),'invalid player')
    rejects(lambda:lottery_values(F(1,2),F(1,2),0,(0,1)),'missing punishment action')
    rejects(lambda:reputation_tree(F(1,3),F(3,2),0,(1,F(1,6),1),(0,0,0),F(4,5)),'impossible rational fight mix')
    rejects(lambda:reputation_tree(F(1,3),F(1,2),0,(1,F(1,6)),(0,0,0),F(4,5)),'missing public-history continuation')
    for text in ('{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}'):
        rejects(lambda text=text:json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant),'strict JSON')
    eq(reader.anchors,anchors,'every printed exact calculation anchor')
    eq(tuple(p.read_bytes() for p in paths),before,'four runtime files unchanged')
    result={'chapter':'v13-c07','status':'passed','worked_cases':6,'solved_exercises':12,
            'numeric_anchors':len(anchors),**counts,'runtime_payloads':list(FILES),'writes':0,
            'scope':'Original finite path/policy oracles and bindings; unrestricted proofs audited separately.'}
    json.dumps(result,allow_nan=False)
    return result


if __name__=='__main__':
    need(len(sys.argv)==1,'CLI accepts no arguments and writes nothing')
    check()

"""Teaching capstone author oracle: feasible production, exact utility and raw-row least squares."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isqrt
import ast
import json
FILES=('content/cross-assessments/teaching-portfolio.html','scripts/check_teaching_portfolio.py','content/reviews/teaching-portfolio-sources.json','content/reviews/teaching-portfolio-author.json')
def require(ok,message):
    if not ok: raise ValueError(message)


def numeric(text):
    text=text.rsplit('=',1)[-1].strip().replace('−','-')
    def walk(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return F(str(node.value))
        if isinstance(node,ast.Tuple):return tuple(walk(x) for x in node.elts)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):return -walk(node.operand)
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return walk(node.left)/walk(node.right)
        raise ValueError('restricted rational syntax')
    return walk(ast.parse(text,mode='eval').body)


class BaseManuscript(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1=0;self.artifacts=[];self.forms=[];self.stack=[];self.ids=[];self.inputs={};self.results={};self.prompts={};self.solutions={};self.sources={};self.worked=[];self.rows=[];self.row=None;self.cell=None;self.links=set();self.guides=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='h1':self.h1+=1
        if 'data-artifact' in a:self.artifacts.append(a['data-artifact'])
        if 'data-form' in a:self.forms.append(a['data-form'])
        for attr,dest in (('data-input',self.inputs),('data-result',self.results)):
            if attr in a:require(a[attr] not in dest,'duplicate marker');dest[a[attr]]=''
        if tag=='article' and 'worked' in a.get('class','').split():self.worked.append(a['id'])
        if tag=='li' and any(t=='ol' and 'exercises' in x.get('class','').split() for t,x in self.stack):self.prompts[a['id']]=''
        if 'data-solution-for' in a:
            require(any(t=='details' and 'solutions' in x.get('class','').split() for t,x in self.stack),'solution disclosure')
            require(a['data-solution-for'] not in self.solutions,'unique solution');self.solutions[a['data-solution-for']]=''
        if 'data-source' in a:require(a['data-source'] not in self.sources,'unique source');self.sources[a['data-source']]=a['href']
        if tag=='a':self.links.add(a['href'])
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
        if tag not in ('br','hr','img'):self.stack.append((tag,a))
    def handle_data(self,text):
        if self.cell is not None:self.cell+=text
        for tag,a in self.stack:
            if 'data-input' in a:self.inputs[a['data-input']]+=text
            if 'data-result' in a:self.results[a['data-result']]+=text
            if tag=='li' and a.get('id') in self.prompts:self.prompts[a['id']]+=text
            if 'data-solution-for' in a:self.solutions[a['data-solution-for']]+=text
    def handle_endtag(self,tag):
        require(self.stack and self.stack[-1][0]==tag,'HTML nesting')
        if tag in ('td','th'):self.row.append(self.cell);self.cell=None
        if tag=='tr':self.rows.append(self.row);self.row=None
        self.stack.pop()


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def production(capacity,cloth):
    require(len(capacity)==4,'two producers/capacity pairs')
    aw,ac,bw,bc=map(F,capacity);cloth=F(cloth)
    require(all(v>0 for v in (aw,ac,bw,bc)) and 0<=cloth<=ac+bc,'positive capacity and feasible cloth requirement')
    endpoints=(max(F(0),cloth-bc),min(ac,cloth))
    candidates=tuple((ca,cloth-ca,aw*(1-ca/ac)+bw*(1-(cloth-ca)/bc)) for ca in sorted(set(endpoints)))
    best=max(v[2] for v in candidates)
    return tuple(row for row in candidates if row[2]==best)


def rational_sqrt(value):
    value=F(value);require(value>=0,'nonnegative wealth')
    a,b=isqrt(value.numerator),isqrt(value.denominator)
    require(a*a==value.numerator and b*b==value.denominator,'oracle cases require an exact rational square root')
    return F(a,b)


def lottery(low,high,p):
    low,high,p=map(F,(low,high,p));require(0<=p<=1,'probability domain')
    eu=p*rational_sqrt(low)+(1-p)*rational_sqrt(high)
    ew=p*low+(1-p)*high;ce=eu*eu
    return ew,eu,ce,ew-ce


def replacement(ce,offer,fee):
    ce,offer,fee=map(F,(ce,offer,fee));require(ce>=0 and offer>=0 and 0<=fee<=offer,'nonnegative feasible replacement wealth')
    return (offer-fee>ce)-(offer-fee<ce)


def mean(values):
    require(len(values)>0 and all(type(v) in (int,F) for v in values),'nonempty exact observations')
    return sum(values,F(0))/len(values)


def covariance(x,y):
    require(len(x)==len(y)>0,'paired observations')
    mx,my=mean(x),mean(y)
    return sum(((a-mx)*(b-my) for a,b in zip(x,y)),F(0))/len(x)


def ols(y,*columns):
    n=len(y);require(n>0 and columns and all(len(c)==n for c in columns),'full common regression rows')
    mean(y)
    for c in columns:mean(c)
    design=[tuple(F(v) for v in (1,*row)) for row in zip(*columns)];k=len(columns)+1
    augmented=[[sum((row[i]*row[j] for row in design),F(0)) for j in range(k)]+[sum((row[i]*target for row,target in zip(design,y)),F(0))] for i in range(k)]
    for col in range(k):
        pivot=next((r for r in range(col,k) if augmented[r][col]),None)
        require(pivot is not None,'rank deficient normal equations')
        augmented[col],augmented[pivot]=augmented[pivot],augmented[col]
        divisor=augmented[col][col];augmented[col]=[v/divisor for v in augmented[col]]
        for r in range(k):
            if r!=col:
                factor=augmented[r][col];augmented[r]=[a-factor*b for a,b in zip(augmented[r],augmented[col])]
    return tuple(row[-1] for row in augmented)


def binary_bounds(total,initial,respondents,success):
    require(all(type(v) is int for v in (total,initial,respondents,success)) and total>0 and 0<=initial<=total and 0<respondents<=total and 0<=success<=respondents,'binary roster domain')
    lo,hi=F(success,total),F(success+total-respondents,total);base=F(initial,total)
    return base,F(success,respondents),lo,hi,lo-base,hi-base


def audit(doc):
    count=0
    def eq(a,b,label):
        nonlocal count
        require(a==b,label);count+=1
    x={k:numeric(v) for k,v in doc.inputs.items()}
    expected={'production':(12,6,8,8),'cloth':10,'utility':(64,144,F(1,2),104),'fresh-utility':(36,100,F(1,2),68),'regression':((-1,-1,1,1),(-1,1,1,3),(-3,-1,3,5)),'fresh-z':(-1,1,-1,1),'defense-roster':(5,1,4,3)}
    eq(x,expected,'actual visible primitive groups')
    cap=x['production'];ca,cb,w=production(cap,x['cloth'])[0];aw,ac,bw,bc=cap
    low,high,prob,offer=x['utility'];u=lottery(low,high,prob);ua=lottery(low,high,F(1,4));fl,fh,fp,fo=x['fresh-utility'];fresh=lottery(fl,fh,fp)
    xx,zz,yy=x['regression'];means=tuple(map(mean,(xx,zz,yy)));vx=covariance(xx,xx);vz=covariance(zz,zz);cxz=covariance(xx,zz);cxy=covariance(xx,yy);short=ols(yy,xx);full=ols(yy,xx,zz);zx=ols(xx,zz);xr=tuple(v-zx[0]-zx[1]*z for v,z in zip(xx,zz));rxvar=covariance(xr,xr);rxy=covariance(xr,yy)
    znew=x['fresh-z'];ynew=tuple(2*a+b for a,b in zip(xx,znew));nf=ols(ynew,xx,znew)
    residual1=tuple(3*a+b for a,b in zip(xx,znew));residual2=tuple(4*a+b for a,b in zip(xx,znew))
    a9,b9,w9=production(cap,9)[0]
    want={'production-key':(ca,cb,w,ca/ac,w/aw,cb/bc,production(cap,0)[0][2],production(cap,8)[0][2],production(cap,14)[0][2]),'production-scores':((1,1,1,1,1),(1,1,0,0,0),5,2,F(2,6)+F(12,12)),'utility-key':(u[0],u[1],u[2],offer-u[2]),'utility-alternative':ua,'utility-scores':((1,0,0,0,0),(1,1,1,1,1),(1,1,0,1,0),(1,5,3)),'utility-fresh':(fresh[0],fresh[1],fresh[2],fo-fresh[2]),'regression-key':(means,(vx,vz,cxz,cxy),(short[1],short[0]),xr,(rxvar,rxy),(full[1],full[2],full[0])),'regression-fresh':(ynew,mean(xx),mean(znew),mean(ynew),covariance(xx,xx),covariance(znew,znew),covariance(xx,znew),ols(ynew,xx)[1],nf[1],nf[2],nf[0]),'regression-residual':(residual1,covariance(xx,xx)/vx,ols(residual1,xx)[1]),'regression-scores':((1,1,1,0,0),(1,1,1,1,1),3,5),'defense-production':(a9,b9,w9,a9/ac,w9/aw),'defense-evidence':binary_bounds(*(int(v) for v in x['defense-roster'])),'defense-residual':(residual2,covariance(xx,tuple(2*v for v in xx))/vx,ols(residual2,xx)[1])}
    eq(set(want),set(doc.results),'all displayed result groups')
    for k,v in want.items():eq(numeric(doc.results[k]),v,'visible '+k)
    eq((aw/4,ac/4),(3,F(3,2)),'quarter-time prerequisite')
    for cloth in (F(0),F(6),F(8),F(9),F(10),F(14)):
        ca,cb,w=production(cap,cloth)[0]
        eq(ca+cb,cloth,'cloth allocation meets exact requirement')
        eq(w,20-cloth if cloth<=8 else 28-2*cloth,'piecewise frontier witness')
        eq((ca/ac+(aw-aw/ac*ca)/aw,cb/bc+(bw-bw/bc*cb)/bw),(1,1),'both time accounts')
    eq((max(F(0),10-bc),min(ac,F(10))),(2,6),'full feasible interval for C10')
    # The exact linear objective slope on this interval is -1; minimum feasible A-cloth gives global optimum.
    eq(bw/bc-aw/ac,-1,'global allocation objective coefficient')
    eq((20-8,28-2*8),(12,12),'frontier kink continuity')
    eq(production((12,6,16,8),8),((0,8,12),(6,2,12)),'equal opportunity costs: both endpoints optimal and intervening linear objective constant')
    eq(production((12,6,24,8),8),((6,2,18),),'reversed comparative advantage')
    eq((u[2],u[0],u[3]),(100,104,4),'nondegenerate risk premium')
    for p in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
        ew,eu,ce,prem=lottery(low,high,p)
        eq(prem,p*(1-p)*(rational_sqrt(high)-rational_sqrt(low))**2,'global premium expansion')
        eq(prem,4-16*(p-F(1,2))**2,'completed square maximum witness')
    eq((lottery(100,100,F(1,3))[3],lottery(0,0,F(1,2))[3]),(0,0),'equal wealth and zero-wealth boundaries')
    for fee,decision in ((F(0),1),(F(4),0),(F(5),-1),(F(104),-1)):
        eq(replacement(u[2],offer,fee),decision,'fee boundary and feasible offer')
    eq(replacement(ua[2],offer,0),-1,'changed probability rejects unchanged104 even without fee')
    eq(replacement(ua[2],ua[0],3),0,'changed expected wealth fee3 indifference')
    oldgrades=[int(row[-1]) for row in doc.rows if len(row)==3 and row[0] in ('J','K','L')]
    eq(oldgrades,[5,2,2],'actual erroneous grades read')
    eq((tuple(new-old for new,old in zip((1,5,3),oldgrades)),sum(oldgrades),sum((1,5,3))),((-4,3,1),9,9),'individual corrections cannot be inferred from unchanged aggregate grade total')
    eq(tuple(v-mean(xx) for v in xx),(-1,-1,1,1),'full centered X')
    eq(tuple(v-mean(zz) for v in zz),(-2,0,0,2),'full centered Z')
    eq(tuple(v-mean(yy) for v in yy),(-4,-2,2,4),'full centered Y')
    eq(tuple(2*a+b for a,b in zip(xx,zz)),yy,'raw generating algebra')
    eq((mean(xr),covariance(xr,zz)),(0,0),'residual orthogonality')
    eq(vx*vz-cxz*cxz,1,'positive full normal-equation determinant')
    eq(tuple(full[0]+full[1]*a+full[2]*b for a,b in zip(xx,zz)),yy,'all four full fitted values')
    eq(short[1],2+cxz/vx,'original omitted-variable term')
    for epsilon in ((0,0,0,0),xx,tuple(2*v for v in xx),tuple(v+3 for v in xx)):
        target=tuple(2*a+b+e for a,b,e in zip(xx,znew,epsilon))
        eq(ols(target,xx)[1],2+covariance(xx,znew)/vx+covariance(xx,epsilon)/vx,'full residual-term identity including nonzero residual mean')
    for shift in (F(-3),F(0),F(1,2),F(4)):
        eq(tuple((2+shift)*v+(1-shift)*v for v in xx),tuple(3*v for v in xx),'complete collinear coefficient family witness')
        eq(tuple((4-2*shift)*v+shift*2*v for v in xx),tuple(4*v for v in xx),'defense doubled-column family witness')
    # Families follow from coefficient-sum identities for arbitrary real shift; no finite grid is claimed as proof.
    eq((2+1,4-2*F(3,2)+2*F(3,2)),(3,4),'coefficient cancellation identity')
    ev=binary_bounds(5,1,4,3);eq(tuple(F(3+m,5) for m in (0,1)),ev[2:4],'attainable binary missing learner endpoints')
    eq((sum((3,5,5,5,2)),sum((4,4,4,3)),sum((5,5,5,5)),sum((5,15,10,10,5))),(20,15,20,45),'case and defense time budgets')
    eq((3*(1+2),3*(F(3,2)+F(3,2)),25+25+50,30+30+40,4*30),(9,9,100,100,120),'both whole course workload/weights and mentoring minutes')
    invalid=[lambda:production(cap,-1),lambda:production(cap,15),lambda:production((12,0,8,8),4),lambda:lottery(-1,144,F(1,2)),lambda:lottery(64,-1,F(1,2)),lambda:lottery(64,144,F(-1,10)),lambda:lottery(64,144,F(11,10)),lambda:replacement(100,104,-1),lambda:replacement(100,104,105),lambda:ols(yy,(1,1,1,1)),lambda:ols(tuple(3*v for v in xx),xx,xx),lambda:ols(yy,(1,2)),lambda:binary_bounds(5,1,0,0),lambda:binary_bounds(5,1,4,5),lambda:binary_bounds(5,6,4,3)]
    for fn in invalid:
        try:fn()
        except ValueError:pass
        else:raise ValueError('invalid domain accepted')
    return count,len(invalid),len(want)


def check(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    raw={f:(root/f).read_bytes() for f in FILES};review=strict_json(raw[FILES[3]]);sources=strict_json(raw[FILES[2]])
    require(set(review['payloads'])==set(FILES[:3]),'three nonself frozen bindings')
    for f,v in review['payloads'].items():require(v=={'bytes':len(raw[f]),'sha256':sha256(raw[f]).hexdigest()},'frozen file changed '+f)
    d=BaseManuscript();d.feed(raw[FILES[0]].decode());require(not d.stack and d.h1==1 and len(d.ids)==len(set(d.ids)),'balanced standalone one-h1 fragment')
    require(d.artifacts==['syllabi','lessons_assessment','learner_work','observation','supervision','reflection_defense'],'six required artifact groups')
    require(d.forms==['intake','syllabus','observation','learner_work','supervision','decision'],'six complete blank form groups')
    require(d.worked==[f'teaching-case-{i}' for i in range(1,4)],'three calibration dossiers')
    ids={f'teaching-case-task-{i}' for i in range(1,4)}|{f'teaching-defense-{i}' for i in range(1,7)}
    require(set(d.prompts)==set(d.solutions)==set(review['exact_task_review'])==ids,'nine actual tasks and full answer guides')
    for k,v in review['exact_task_review'].items():require(v['prompt_sha256']==sha256(d.prompts[k].encode()).hexdigest() and v['solution_sha256']==sha256(d.solutions[k].encode()).hexdigest(),'reviewed exact task changed')
    routes={'teaching-bok-syllabus':'https://bokcenter.harvard.edu/syllabus-design','teaching-cmu-rubrics':'https://www.cmu.edu/teaching/designteach/teach/rubrics.html','teaching-cmu-observation':'https://www.cmu.edu/teaching/assessment/assessteaching/classroomObservations.html','teaching-ori-responsibilities':'https://ori.hhs.gov/content/Chapter-7-Mentor-and-Trainee-Responsibilities-Basic-responsibilities'}
    require(d.sources==routes=={s['id']:s['url'] for s in sources['sources']},'four exact bounded source routes')
    local={v for v in d.links if not v.startswith('https://')}
    require(local=={f'v17-c{i:02d}.html' for i in range(1,13)}|{'v16-assessment.html','v17-assessment.html','v17-assessment.html#project'},'all12 chapter and both volume/remediation routes')
    comparisons,invalid,groups=audit(d)
    return {'assessment':'teaching-portfolio','status':'passed author checks','runtime_files':4,'artifact_groups':6,'blank_form_groups':6,'calibration_dossiers':3,'defense_prompts':6,'full_task_solution_pairs':9,'numeric_groups':groups,'comparisons':comparisons,'invalid_domains':invalid,'source_routes':4,'v17_chapter_routes':12,'scope':'Protocol and three fictional calibration dossiers fully reviewed; actual learner teaching, permissions and qualified independent human evaluation remain required.'}


if __name__=='__main__':
    check()

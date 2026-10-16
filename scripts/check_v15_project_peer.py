"""Independent primitive policy laboratory oracle; never runs author checker."""
from pathlib import Path
from fractions import Fraction as F
from hashlib import sha256
from html.parser import HTMLParser
from itertools import product
from math import isfinite
import ast,json,copy,io,contextlib,runpy,tempfile,subprocess,sys,os
FILES=('content/assessments/parts/v15-project.html','content/projects/v15-assessment-inputs.json','content/projects/v15-assessment-analysis.py','content/projects/v15-assessment-output.json','content/projects/v15-assessment-manifest.json','content/projects/v15-assessment-README.txt','scripts/check_v15_project.py','content/reviews/v15-project-sources.json','content/reviews/v15-project-author.json','scripts/check_v15_project_peer.py','content/reviews/v15-project-peer.json')
def ensure(x,msg):
    if not x:raise ValueError(msg)
def num(v):
    ensure(type(v) in (int,str,F),'exact nonboolean primitive')
    try:return F(v)
    except (ValueError,ZeroDivisionError):raise ValueError('rational primitive')
def strict(raw):
    def pairs(rows):
        d={}
        for k,v in rows:ensure(k not in d,'unique JSON key');d[k]=v
        return d
    def fail(s):raise ValueError('finite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=fail)
def primitive_model(data):
    ensure(data['schema']=='v15-policy-lab-1' and data['synthetic'] is True,'schema');gs=data['groups'];ensure(len(gs)==4 and len({g['id'] for g in gs})==4,'four distinct unit groups');groups=[]
    for g in gs:
        mass,y,v,h,w=map(num,(g['mass'],g['income'],g['productivity_offset'],g['damage_share'],g['welfare_weight']));ensure(mass==1 and y>=0 and v>=0 and h>=0 and w>0,'group domains');groups.append((g['id'],y,v,h,w))
    ensure(sum(g[3] for g in groups)==1,'damage shares sum');tech={k:num(v) for k,v in data['technology'].items()};ensure(min(tech.values())>=0 and tech['abatement_reduction']<=tech['emissions'],'technology');cap=num(data['treasury']['reserve_limit']);ensure(cap>=0 and data['treasury']['refund_rule']=='equal_per_person','reserve');menu=data['menu']
    for k,vals in menu.items():ensure(len(vals)>0 and len(set(vals))==len(vals) and all(type(v)is int and v>=0 for v in vals),'integer distinct menu')
    ensure(0 in menu['capacity'] and max(menu['capacity'])<=4 and set(menu['abatement'])<={0,1},'capacity menu')
    u=data['uncertainty'];effects=tuple(map(num,u['effects']));damages=tuple(map(num,u['damages']));pw=tuple(map(num,u['effect_weights']));dw=tuple(map(num,u['damage_weights']));ensure(len(effects)==len(pw)>0 and len(damages)==len(dw)>0 and len(set(effects))==len(effects) and len(set(damages))==len(damages),'state dimensions');ensure(min(effects)>=0 and min(damages)>=0 and min(pw)>0 and min(dw)>0 and sum(pw)==sum(dw)==1,'state probability domains');states=[(t,d,pw[i]*dw[j]) for i,t in enumerate(effects) for j,d in enumerate(damages)];policies=[(0,0,0,0)]+[(k,f,s,a) for k,f,s,a in product(menu['capacity'],menu['fee'],menu['subsidy'],menu['abatement']) if k>0];ensure(len(policies)==len(set(policies)),'policy uniqueness');return groups,tech,cap,states,policies

def row(groups,tech,limit,policy,state):
    k,fee,sub,abat=policy;theta,damage,prob=state;N=len(groups);R=k*(tech['capacity_cost']+tech['administration']+sub)+abat*tech['abatement_cost'];levy=R/N;reasons=[]
    if R>limit:reasons.append('reserve_limit')
    applicants=[i for i,g in enumerate(groups) if theta+g[2]-tech['travel']-fee+sub>=0];admitted=applicants[:k];m=len(admitted);output=sum(theta+groups[i][2] for i in admitted);travel=m*tech['travel'];E=m*(tech['emissions']-abat*tech['abatement_reduction']);D=damage*E;C=k*tech['capacity_cost']+m*tech['administration']+abat*tech['abatement_cost'];subsidy=m*sub;fees=m*fee;expenses=C+subsidy;refund=R+fees-expenses
    if any(g[1]-levy<0 for g in groups):reasons.append('initial_cash')
    if k>0 and any(g[1]-levy<max(0,fee-sub) for g in groups):reasons.append('participant_cash')
    delta=[(theta+g[2]-tech['travel']-fee+sub if i in admitted else 0)-levy+refund/N-g[3]*D for i,g in enumerate(groups)];cons=[g[1]+v for g,v in zip(groups,delta)]
    if min(cons)<0:reasons.append('final_consumption')
    if refund<0:reasons.append('treasury_deficit')
    weighted=sum(g[4]*v for g,v in zip(groups,delta));resource=sum(delta);ensure(resource==output-travel-C-D,'universal resource ledger');ensure(R+fees==expenses+refund,'treasury');return dict(policy=policy,state=state,feasible=not reasons,reasons=reasons,R=R,levy=levy,applicants=[groups[i][0] for i in applicants],admitted=[groups[i][0] for i in admitted],m=m,output=output,travel=travel,E=E,D=D,C=C,subsidy=subsidy,fees=fees,expenses=expenses,refund=refund,delta=delta,cons=cons,W=weighted,G=resource)

def oracle(data):
    groups,tech,cap,states,policies=primitive_model(data);matrix={p:[row(groups,tech,cap,p,s) for s in states] for p in policies};feasible=[p for p in policies if all(z['feasible'] for z in matrix[p])];ensure(feasible,'nonempty admissible menu');front=[max(matrix[p][i]['W'] for p in feasible) for i in range(len(states))];expected={p:sum(s[2]*r['W'] for s,r in zip(states,matrix[p])) for p in feasible};resources={p:sum(s[2]*r['G'] for s,r in zip(states,matrix[p])) for p in feasible};regrets={p:tuple(v-r['W'] for v,r in zip(front,matrix[p])) for p in feasible};worst={p:max(v) for p,v in regrets.items()};choose=lambda vals,best:[p for p in feasible if vals[p]==best(vals.values())];minstate=min(s[0] for s in states);maxstate=max(s[0] for s in states);lines={}
    for p in feasible:
        ends=[]
        for theta in (minstate,maxstate):
            subset=[(s,r) for s,r in zip(states,matrix[p]) if s[0]==theta];mass=sum(s[2] for s,r in subset);ends.append(sum(s[2]*r['W'] for s,r in subset)/mass)
        lines[p]=(ends[0],ends[1]-ends[0])
    support={}
    for p,(a,b) in lines.items():
        lower,upper=F(0),F(1);empty=False
        for q,(c,d) in lines.items():
            slope=b-d;intercept=a-c
            if slope>0:lower=max(lower,-intercept/slope)
            elif slope<0:upper=min(upper,-intercept/slope)
            elif intercept<0:empty=True
        if not empty and lower<=upper:support[p]=(lower,upper)
    return dict(groups=groups,states=states,policies=policies,matrix=matrix,feasible=feasible,front=front,expected=expected,resources=resources,regrets=regrets,worst=worst,expected_opt=choose(expected,max),resource_opt=choose(resources,max),robust_opt=choose(worst,min),state_opt=[[p for p in feasible if matrix[p][i]['W']==front[i]] for i in range(len(states))],lines=lines,support=support)
def pack(x):
    if isinstance(x,F):return int(x) if x.denominator==1 else str(x)
    if isinstance(x,dict):return {k:pack(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [pack(v) for v in x]
    return x
def pid(p):return 'K%dF%dS%dA%d'%p
def sid(s):return 'T'+str(s[0])+'D'+str(s[1])
def output_from_oracle(data,own):
    rows=[];g=own['groups'];ids=[z[0] for z in g]
    for p in own['policies']:
        rs=own['matrix'][p];r=rs[0];pre=[x[1]-r['levy'] for x in g];early=[]
        if 'reserve_limit'in r['reasons']:early.append('reserve_limit')
        if 'initial_cash'in r['reasons']:early.append('initial_consumption')
        if 'participant_cash'in r['reasons']:early.append('upfront_user_charge')
        result={'id':pid(p),'action':p,'reserve':r['R'],'levy':r['levy'],'initial_cash':pre,'feasible':p in own['feasible'],'diagnostics':early,'states':[]}
        if not early:
            for s,r in zip(own['states'],rs):
                errors=[reason for reason in r['reasons'] if reason=='final_consumption'];result['states'].append({'state':sid(s),'wants':[i in r['applicants'] for i in ids],'admitted':[i in r['admitted'] for i in ids],'participants':r['m'],'production':r['output'],'travel':r['travel'],'emissions':r['E'],'damage_loss':r['D'],'real_public_cost':r['C'],'expenses':r['expenses'],'fees':r['fees'],'refund':r['refund'],'consumption':r['cons'],'delta':r['delta'],'resource_gain':r['G'],'weighted_gain':r['W'],'feasible':not errors,'diagnostics':errors})
                if errors:result['diagnostics'].append(sid(s)+':'+','.join(errors))
        if p in own['feasible']:result.update(regrets=own['regrets'][p],max_regret=own['worst'][p],expected_weighted=own['expected'][p],expected_resource=own['resources'][p])
        rows.append(result)
    select=lambda field,chosen:{'value':own[field][own[chosen][0]],'policies':sorted(map(pid,own[chosen]))}
    ev=data['evidence'];gap=num(ev['train_treated'])-num(ev['train_untreated']);bounds=tuple(map(num,ev['selection_bound']));fits=[]
    for theta in map(num,data['uncertainty']['effects']):
        sel=gap-theta;train=num(ev['baseline_intercept'])+num(ev['baseline_slope'])*num(ev['train_x'])+theta+sel;holdout=num(ev['baseline_intercept'])+num(ev['baseline_slope'])*num(ev['holdout_x'])+theta+sel;fits.append(dict(effect=theta,selection=sel,inside_selection_bound=bounds[0]<=sel<=bounds[1],train_prediction=train,train_error=train-num(ev['train_treated']),holdout_prediction=holdout,holdout_error=holdout-num(ev['holdout_treated'])))
    wrong=num(ev['baseline_intercept'])+2*num(ev['baseline_slope'])*num(ev['holdout_x'])+gap
    result={'schema':'v15-policy-output-1','states':[dict(id=sid(s),effect=s[0],damage=s[1],weight=s[2]) for s in own['states']],'policy_count':len(rows),'uniformly_feasible_count':len(own['feasible']),'policies':rows,'state_frontiers':[dict(state=sid(s),best=v,policies=sorted(map(pid,opts))) for s,v,opts in zip(own['states'],own['front'],own['state_opt'])],'expected_weighted_optimum':select('expected','expected_opt'),'expected_resource_optimum':select('resources','resource_opt'),'minimax_regret':select('worst','robust_opt'),'forecast_envelope':[dict(policy=pid(p),intercept=own['lines'][p][0],slope=own['lines'][p][1],q_interval=own['support'][p]) for p in own['support']],'evidence':dict(identified_sum=gap,causal_interval=(gap-bounds[1],gap-bounds[0]),fits=fits,wrong_slope_holdout_prediction=wrong,wrong_slope_holdout_error=wrong-num(ev['holdout_treated']))};return pack(result)

def literal(s):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return tuple(walk(x) for x in n.elts)
        if isinstance(n,ast.Constant) and type(n.value)in(int,float):return F(str(n.value))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -walk(n.operand)
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal only')
    return walk(ast.parse(s.split('=')[-1].strip(),mode='eval').body)
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=set();self.prompts=[];self.answers={};self.rubrics={};self.mark={};self.sources={};self.links=[]
    def handle_starttag(self,t,attrs):
        a=dict(attrs);ensure(len(a)==len(attrs),'unique attributes')
        if 'id'in a:ensure(a['id'] not in self.ids and (a['id']=='project' or a['id'].startswith('project-')),'unique IDs');self.ids.add(a['id'])
        if t=='li' and any(t=='ol' and 'exercises'in d.get('class','').split() for t,d in self.stack):self.prompts.append(a['id'])
        if 'data-solution-for'in a:
            k=a['data-solution-for'];ensure(k not in self.answers and any(t=='details' and 'solutions'in d.get('class','').split() for t,d in self.stack),'disclosed answers');self.answers[k]=''
        if 'data-rubric-domain'in a:ensure(a['data-rubric-domain'] not in self.rubrics,'unique rubric');self.rubrics[a['data-rubric-domain']]=int(a['data-points'])
        for key in ('data-input','data-result'):
            if key in a:ensure(a[key] not in self.mark,'unique marker');self.mark[a[key]]=''
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        elif t=='a':self.links.append(a['href'])
        if t not in ('br','hr','img','input','meta','link'):self.stack.append((t,a))
    def handle_data(self,s):
        for t,a in self.stack:
            if 'data-solution-for'in a:self.answers[a['data-solution-for']]+=s
            for k in ('data-input','data-result'):
                if k in a:self.mark[a[k]]+=s
    def handle_endtag(self,t):ensure(self.stack and self.stack[-1][0]==t,'balanced markup');self.stack.pop()

def reader_gates(raw,expected):
    names=[Path(f).name for f in FILES[1:6]];runs=aliases=parser_rejections=0
    with tempfile.TemporaryDirectory(prefix='v15-project-peer-reader-',dir='/private/tmp') as temporary:
        folder=Path(temporary)
        for name,f in zip(names,FILES[1:6]):(folder/name).write_bytes(raw[f])
        before={name:(folder/name).read_bytes() for name in names};ensure(set(p.name for p in folder.iterdir())==set(names),'five-file capsule')
        for optimized in (False,True):
            command=[sys.executable,'-B']+(['-O'] if optimized else [])+[str(folder/names[1])]
            response=subprocess.run(command,cwd='/',capture_output=True,text=True);ensure(response.returncode==0 and not response.stdout and not response.stderr,'default silent reader');ensure(strict((folder/names[2]).read_bytes())==expected,'reader full independent output');ensure(before=={name:(folder/name).read_bytes() for name in names} and set(p.name for p in folder.iterdir())==set(names),'five reader bytes/membership unchanged');runs+=1
            with tempfile.TemporaryDirectory(prefix='v15-project-peer-explicit-',dir='/private/tmp') as extra:
                output=Path(extra)/'explicit.json';response=subprocess.run(command+[str(folder/names[0]),str(output)],cwd='/',capture_output=True,text=True);ensure(response.returncode==0 and not response.stdout and not response.stderr and strict(output.read_bytes())==expected,'explicit reader output');runs+=1
                for protected in (names[0],names[1],names[3],names[4]):
                    target=folder/protected
                    for kind in ('existing','resolved','symlink','hardlink'):
                        alias=Path(extra)/(kind+'-'+protected)
                        if kind=='existing':alias=target
                        elif kind=='resolved':alias=folder/'..'/folder.name/protected
                        elif kind=='symlink':alias.symlink_to(target)
                        else:os.link(target,alias)
                        response=subprocess.run(command+[str(folder/names[0]),str(alias)],cwd='/',capture_output=True,text=True);ensure(response.returncode!=0 and not response.stdout,'protected alias rejected');ensure(before=={name:(folder/name).read_bytes() for name in names},'protected bytes remain');aliases+=1
            for args in (['--unexpected'],['a','b','c']):
                response=subprocess.run(command+args,cwd='/',capture_output=True,text=True);ensure(response.returncode!=0 and not response.stdout,'parser rejects malformed CLI');parser_rejections+=1
            ensure(before=={name:(folder/name).read_bytes() for name in names} and set(p.name for p in folder.iterdir())==set(names),'reader final immutable capsule')
    return runs,aliases,parser_rejections

def check(root=None):
    base=Path(root) if root is not None else Path(__file__).resolve().parents[1];raw={f:(base/f).read_bytes() for f in FILES};peer=strict(raw[FILES[10]]);author=strict(raw[FILES[8]]);sources=strict(raw[FILES[7]]);manifest=strict(raw[FILES[4]]);ensure(set(peer['payload_bindings'])==set(FILES[:10]) and not peer['open_findings'],'ten nonself peer hashes');ensure(set(author['payload_bindings'])==set(FILES[:8]) and not author['open_findings'],'eight author hashes')
    for record in (peer,author):
        for f,b in record['payload_bindings'].items():ensure(len(raw[f])==b['bytes'] and sha256(raw[f]).hexdigest()==b['sha256'],'immutable binding')
    names={Path(f).name:f for f in FILES[1:6]};ensure(set(manifest['payloads'])==set(names)-{Path(FILES[4]).name},'manifest four nonself bindings')
    for name,b in manifest['payloads'].items():ensure(len(raw[names[name]])==b['bytes'] and sha256(raw[names[name]]).hexdigest()==b['sha256'],'reader manifest')
    data=strict(raw[FILES[1]]);own=oracle(data);expected=output_from_oracle(data,own);count=0
    def same(a,b):
        nonlocal count
        if isinstance(b,dict):ensure(isinstance(a,dict) and set(a)==set(b),'full output keys');[same(a[k],v) for k,v in b.items()]
        elif isinstance(b,(tuple,list)):
            ensure(isinstance(a,(tuple,list)) and len(a)==len(b),'output length')
            for c,e in zip(a,b):same(c,e)
        else:ensure(type(a)==type(b) and a==b,'exact field '+str((a,b)));count+=1
    same(strict(raw[FILES[3]]),expected);parser=Read();parser.feed(raw[FILES[0]].decode());parser.close();tasks=[f'project-task{i}' for i in range(1,8)];ensure(not parser.stack and parser.prompts==list(parser.answers)==tasks and all(len(v)>900 for v in parser.answers.values()),'seven complete solutions');ensure(set(peer['exact_task_review'])==set(tasks),'full peer task audit');ensure(parser.rubrics=={k:20 for k in ('evidence','feasibility','accounts','decision','transfer')},'five additive domains');ensure(set(parser.links)==set(names),'reader routes');ensure(parser.sources=={s['id']:s['url'] for s in sources['sources']},'source routes');ensure('All other28'in raw[FILES[0]].decode(),'support count repair')
    one=(1,0,1,1);two=(2,0,1,1);zero=(0,0,0,0);row0=own['matrix'][two][0];threshold=own['matrix'][(3,2,0,0)];ev=expected['evidence'];mean=sum(s[0]*s[2] for s in own['states']);technology=data['technology'];marked={'project-population':tuple(tuple(num(g[key]) for g in data['groups']) for key in ('income','productivity_offset','damage_share','welfare_weight')),'project-technology':tuple(num(technology[key]) for key in ('capacity_cost','administration','travel','abatement_cost','emissions','abatement_reduction'))+(num(data['treasury']['reserve_limit']),),'project-states':tuple(s[2] for s in own['states']),'project-fit':tuple(num(v) for v in (ev['identified_sum'],*ev['causal_interval'],ev['fits'][0]['holdout_prediction'],ev['wrong_slope_holdout_prediction'],ev['wrong_slope_holdout_error'])),'project-threshold':tuple(num(v) for v in (threshold[0]['m'],threshold[2]['m'],threshold[0]['R'],threshold[0]['refund'],threshold[2]['refund'])),'project-feasibility':tuple(map(F,(len(own['policies']),len(own['feasible']),len(own['policies'])-len(own['feasible']))))+(min(c for p in own['feasible'] for r in own['matrix'][p] for c in r['cons']),),'project-account':tuple(num(row0[k]) for k in ('R','levy','m','output','travel','E','D','C','subsidy','expenses','fees','refund','G','W')),'project-frontiers':tuple(own['front']),'project-expected-vector':tuple(r['W'] for r in own['matrix'][one]),'project-objectives':(own['expected'][own['expected_opt'][0]],own['resources'][one],own['resources'][own['resource_opt'][0]],own['expected'][two]),'project-robust-regrets':own['regrets'][two],'project-regret-comparison':tuple(own['worst'][p] for p in (zero,one,two)),'project-switches':(own['support'][zero][1],own['support'][one][1],(mean-1)/2)}
    ensure(set(marked)==set(parser.mark),'all thirteen HTML markers')
    for k,v in marked.items():same(pack(literal(parser.mark[k])),pack(v))
    namespace={'__name__':'v15_project_reader_peer_checked','__file__':str(base/FILES[2])};o=io.StringIO();e=io.StringIO();original=copy.deepcopy(data)
    with contextlib.redirect_stdout(o),contextlib.redirect_stderr(e):exec(compile(raw[FILES[2]],str(base/FILES[2]),'exec'),namespace);actual=namespace['run'](data)
    ensure(not o.getvalue() and not e.getvalue() and data==original,'reader API pure/quiet');same(actual,expected)
    variants=[]
    for path,value in ((('treasury','reserve_limit'),8),(('groups',0,'welfare_weight'),3),(('groups',0,'income'),0),(('technology','travel'),2),(('uncertainty','damages'),[2,100])):
        changed=copy.deepcopy(data);cursor=changed
        for key in path[:-1]:cursor=cursor[key]
        cursor[path[-1]]=value;variants.append(changed)
    for variant in variants:same(namespace['run'](variant),output_from_oracle(variant,oracle(variant)))
    # Check the upper envelope at every pairwise crossing and between successive crossings.
    crossings={F(0),F(1)}
    for a,b in own['lines'].values():
        for c,d in own['lines'].values():
            if b!=d:
                q=(c-a)/(b-d)
                if 0<=q<=1:crossings.add(q)
    knots=sorted(crossings);samples=knots+[(l+h)/2 for l,h in zip(knots,knots[1:])]
    for q in samples:
        maximum=max(a+b*q for a,b in own['lines'].values());winners={p for p,(a,b) in own['lines'].items() if a+b*q==maximum};supported={p for p,(l,h) in own['support'].items() if l<=q<=h};ensure(winners==supported,'global envelope certificate');count+=1
    invalid=[]
    for path,value in ((('groups',0,'mass'),2),(('groups',0,'income'),-1),(('groups',0,'welfare_weight'),0),(('groups',0,'damage_share'),1),(('groups',0,'id'),'P2'),(('technology','travel'),True),(('technology','emissions'),float('nan')),(('technology','abatement_reduction'),2),(('menu','capacity'),[0,5]),(('menu','fee'),[0,0]),(('menu','subsidy'),[0,'1/2']),(('menu','abatement'),[0,2]),(('treasury','reserve_limit'),-1),(('uncertainty','effect_weights'),[1,1,1]),(('uncertainty','damage_weights'),[0,1]),(('uncertainty','effects'),[1,1,3]),(('evidence','selection_bound'),[3,1]),(('evidence','holdout_x'),0),(('conventions','participation'),'strict'),(('synthetic',),False)):
        bad=copy.deepcopy(data);cursor=bad
        for k in path[:-1]:cursor=cursor[k]
        cursor[path[-1]]=value;invalid.append(bad)
    for bad in invalid:
        try:namespace['run'](bad)
        except (ValueError,TypeError,KeyError,ZeroDivisionError):pass
        else:raise ValueError('malformed reader input accepted')
    for f in (lambda:num(True),lambda:num('1/0'),lambda:strict('{"a":1,"a":2}'),lambda:strict('{"a":NaN}'),lambda:literal('2**3')):
        try:f()
        except (ValueError,ZeroDivisionError):pass
        else:raise ValueError('malformed peer input accepted')
    runs,aliases,parser_rejects=reader_gates(raw,expected);ensure(raw=={f:(base/f).read_bytes() for f in FILES},'eleven files immutable');result=dict(volume='v15',component='project_peer',status='passed',tasks=7,points=100,policies=len(own['policies']),uniformly_feasible=len(own['feasible']),states=len(own['states']),comparisons=count,reader_input_rejections=len(invalid),peer_parser_rejections=5,reader_cli_runs=runs,protected_alias_rejections=aliases,reader_cli_parser_rejections=parser_rejects,runtime_files=11);json.dumps(result,allow_nan=False);return result
if __name__=='__main__':check()

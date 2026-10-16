"""Independent exact policy-laboratory author checker; quiet API and CLI."""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
from html.parser import HTMLParser
from hashlib import sha256
import ast,contextlib,copy,io,json,os,subprocess,sys,tempfile
FILES=('content/assessments/parts/v15-project.html','content/projects/v15-assessment-inputs.json','content/projects/v15-assessment-analysis.py','content/projects/v15-assessment-output.json','content/projects/v15-assessment-manifest.json','content/projects/v15-assessment-README.txt','scripts/check_v15_project.py','content/reviews/v15-project-sources.json','content/reviews/v15-project-author.json')
READERS=tuple(Path(p).name for p in FILES[1:6])
def need(x,m):
    if not x:raise ValueError(m)
def rat(x):return F(str(x))
def pack(x):
    if isinstance(x,F):return int(x)if x.denominator==1 else str(x)
    if isinstance(x,dict):return {k:pack(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [pack(v)for v in x]
    return x
class Read(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.ids=[];self.tasks=[];self.solutions=[];self.markers={};self.sources={};self.downloads=[];self.rubrics={}
    def handle_starttag(self,t,a):
        a=dict(a)
        if 'id'in a:self.ids.append(a['id'])
        if t=='li'and any(x=='ol'and 'exercises'in y.get('class','').split()for x,y in self.stack):self.tasks.append(a['id'])
        if 'data-solution-for'in a:
            need(any(x=='details'and 'solutions'in y.get('class','').split()for x,y in self.stack),'disclosed answer');self.solutions.append(a['data-solution-for'])
        if 'data-source'in a:self.sources[a['data-source']]=a['href']
        elif t=='a':self.downloads.append(a['href'])
        if 'data-rubric-domain'in a:self.rubrics[a['data-rubric-domain']]=int(a['data-points'])
        for k in('data-input','data-result'):
            if k in a:need(a[k]not in self.markers,'duplicate marker');self.markers[a[k]]=''
        if t not in('br','hr','img','meta','link','input'):self.stack.append((t,a))
    def handle_endtag(self,t):need(self.stack and self.stack.pop()[0]==t,'balanced HTML')
    def handle_data(self,s):
        for t,a in self.stack:
            for k in('data-input','data-result'):
                if k in a:self.markers[a[k]]+=s

def literal(text):
    def walk(n):
        if isinstance(n,(ast.Tuple,ast.List)):return [walk(x)for x in n.elts]
        if isinstance(n,ast.Constant)and type(n.value)in(int,float):return rat(n.value)
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return-walk(n.operand)
        if isinstance(n,ast.BinOp)and isinstance(n.op,ast.Div):return walk(n.left)/walk(n.right)
        raise ValueError('literal syntax')
    return pack(walk(ast.parse(text.split('=')[-1].strip(),mode='eval').body))

def oracle(data):
    gs=data['groups'];ys=list(map(lambda g:rat(g['income']),gs));v=[rat(g['productivity_offset'])for g in gs];h=[rat(g['damage_share'])for g in gs];w=[rat(g['welfare_weight'])for g in gs];tech={k:rat(x)for k,x in data['technology'].items()};menu=data['menu'];u=data['uncertainty'];thetas=list(map(rat,u['effects']));ds=list(map(rat,u['damages']));ew=list(map(rat,u['effect_weights']));dw=list(map(rat,u['damage_weights']));states=[{'id':f'T{th}D{d}','effect':th,'damage':d,'weight':ew[i]*dw[j]}for i,th in enumerate(thetas)for j,d in enumerate(ds)];actions=[(0,0,0,0)]+list(product([k for k in menu['capacity']if k],menu['fee'],menu['subsidy'],menu['abatement']));records=[]
    for k,f,s,a in sorted(set(actions)):
        R=tech['capacity_cost']*k+(tech['administration']+s)*k+tech['abatement_cost']*a;lev=R/4;initial=[y-lev for y in ys];errors=[]
        if R>rat(data['treasury']['reserve_limit']):errors.append('reserve_limit')
        if min(initial)<0:errors.append('initial_consumption')
        if k and min(initial)<max(0,f-s):errors.append('upfront_user_charge')
        rec={'id':f'K{k}F{f}S{s}A{a}','action':[k,f,s,a],'reserve':R,'levy':lev,'initial_cash':initial,'feasible':not errors,'diagnostics':errors,'states':[]}
        if errors:records.append(rec);continue
        for state in states:
            th,d=state['effect'],state['damage'];ready=[th+x-tech['travel']-f+s>=0 for x in v];candidates=[]
            for z in product((False,True),repeat=4):
                if sum(z)!=min(k,sum(ready))or any(on and not can for on,can in zip(z,ready)):continue
                if any(ready[i]and not z[i]and z[j]for i in range(4)for j in range(i+1,4)):continue
                candidates.append(z)
            need(len(candidates)==1,'unique full active set');z=candidates[0];m=sum(z);output=sum((th+v[i])for i in range(4)if z[i]);travel=tech['travel']*m;pollution=(tech['emissions']-a*tech['abatement_reduction'])*m;harm=d*pollution;C=tech['capacity_cost']*k+tech['administration']*m+tech['abatement_cost']*a;spending=C+s*m;receipts=f*m;refund=R+receipts-spending
            # Each group pays net public cost one quarter; participant transfers stay explicit.
            delta=[(th+v[i]-tech['travel']+s-f)*z[i]-(C+(s-f)*m)/4-h[i]*harm for i in range(4)];consumption=[y+x for y,x in zip(ys,delta)];diagnostics=[]
            if min(consumption)<0:diagnostics.append('final_consumption')
            if m>k:diagnostics.append('capacity')
            rec['states'].append({'state':state['id'],'wants':ready,'admitted':list(z),'participants':m,'production':output,'travel':travel,'emissions':pollution,'damage_loss':harm,'real_public_cost':C,'expenses':spending,'fees':receipts,'refund':refund,'consumption':consumption,'delta':delta,'resource_gain':output-travel-C-harm,'weighted_gain':sum(x*weight for x,weight in zip(delta,w)),'feasible':not diagnostics,'diagnostics':diagnostics})
            if diagnostics:rec['feasible']=False;rec['diagnostics'].append(state['id']+':'+','.join(diagnostics))
        records.append(rec)
    admissible=[r for r in records if r['feasible']];frontiers=[]
    for j,state in enumerate(states):
        maxval=max(r['states'][j]['weighted_gain']for r in admissible);frontiers.append({'state':state['id'],'best':maxval,'policies':sorted(r['id']for r in admissible if r['states'][j]['weighted_gain']==maxval)})
    for rec in admissible:
        vals=[x['weighted_gain']for x in rec['states']];rec['regrets']=[frontiers[j]['best']-val for j,val in enumerate(vals)];rec['max_regret']=max(rec['regrets']);rec['expected_weighted']=sum(v*s['weight']for v,s in zip(vals,states));rec['expected_resource']=sum(x['resource_gain']*s['weight']for x,s in zip(rec['states'],states))
    def select(key,direction):
        b=direction(r[key]for r in admissible);return {'value':b,'policies':sorted(r['id']for r in admissible if r[key]==b)}
    lines={}
    for r in admissible:
        endpoint=[]
        for th in(min(thetas),max(thetas)):endpoint.append(sum(dw[ds.index(st['damage'])]*x['weighted_gain']for st,x in zip(states,r['states'])if st['effect']==th))
        lines[r['id']]=(endpoint[0],endpoint[1]-endpoint[0])
    # Obtain support through all pairwise intersections and midpoint ordering, independently of interval clipping.
    knots={F(0),F(1)}
    for ia,sa in lines.values():
        for ib,sb in lines.values():
            if sa!=sb:
                q=(ib-ia)/(sa-sb)
                if 0<=q<=1:knots.add(q)
    knots=sorted(knots);samples=knots+[(a+b)/2 for a,b in zip(knots,knots[1:])];support={p:[]for p in lines}
    for q in samples:
        values={p:i+b*q for p,(i,b)in lines.items()};best=max(values.values())
        for p,value in values.items():
            if value==best:support[p].append(q)
    envelope=[{'policy':p,'intercept':lines[p][0],'slope':lines[p][1],'q_interval':[min(qs),max(qs)]}for p,qs in support.items()if qs]
    ev=data['evidence'];gap=rat(ev['train_treated'])-rat(ev['train_untreated']);bounds=list(map(rat,ev['selection_bound']));fits=[]
    for th in thetas:
        b=gap-th;pred=[rat(ev['baseline_intercept'])+rat(ev['baseline_slope'])*rat(ev[phase+'_x'])+th+b for phase in('train','holdout')];fits.append({'effect':th,'selection':b,'inside_selection_bound':bounds[0]<=b<=bounds[1],'train_prediction':pred[0],'train_error':pred[0]-rat(ev['train_treated']),'holdout_prediction':pred[1],'holdout_error':pred[1]-rat(ev['holdout_treated'])})
    wrong=rat(ev['baseline_intercept'])+2*rat(ev['baseline_slope'])*rat(ev['holdout_x'])+gap
    return pack({'schema':'v15-policy-output-1','states':states,'policy_count':len(records),'uniformly_feasible_count':len(admissible),'policies':records,'state_frontiers':frontiers,'expected_weighted_optimum':select('expected_weighted',max),'expected_resource_optimum':select('expected_resource',max),'minimax_regret':select('max_regret',min),'forecast_envelope':envelope,'evidence':{'identified_sum':gap,'causal_interval':[gap-bounds[1],gap-bounds[0]],'fits':fits,'wrong_slope_holdout_prediction':wrong,'wrong_slope_holdout_error':wrong-rat(ev['holdout_treated'])}})

def reader_cli(root,expected):
    runs=rejects=0
    for optimized in(False,True):
        with tempfile.TemporaryDirectory(prefix='v15-project-reader-',dir='/private/tmp')as td:
            folder=Path(td)
            for p in FILES[1:6]:(folder/Path(p).name).write_bytes((root/p).read_bytes())
            before={p.name:p.read_bytes()for p in folder.iterdir()};cmd=[sys.executable,'-B']+(['-O']if optimized else[])+[str(folder/READERS[1])]
            good=subprocess.run(cmd,cwd='/',capture_output=True,text=True);need(good.returncode==0 and not good.stdout and not good.stderr,'isolated reader quiet CLI');need(json.loads((folder/READERS[2]).read_text())==expected,'reader output');need({p.name:p.read_bytes()for p in folder.iterdir()}==before,'exact five reader unchanged');runs+=1
            # Explicit paths, then actual direct/resolved, symlink and hardlink protected aliases.
            explicit=folder/'explicit.json';call=subprocess.run(cmd+[str(folder/READERS[0]),str(explicit)],cwd='/',capture_output=True,text=True);need(call.returncode==0 and not call.stdout and not call.stderr and json.loads(explicit.read_text())==expected,'explicit reader CLI');runs+=1
            for name in(READERS[0],READERS[1],READERS[3],READERS[4]):
                target=folder/name
                for kind in('direct','resolved','symlink','hardlink'):
                    if kind=='direct':out=target
                    elif kind=='resolved':out=folder/'..'/folder.name/name
                    elif kind=='symlink':out=folder/('sym-'+name);out.symlink_to(target)
                    else:out=folder/('hard-'+name);os.link(target,out)
                    call=subprocess.run(cmd+[str(folder/READERS[0]),str(out)],cwd='/',capture_output=True,text=True);need(call.returncode!=0 and not call.stdout,'actual alias rejected');need(all((folder/k).read_bytes()==v for k,v in before.items()),'protected bytes changed');rejects+=1
    return runs,rejects

def check(root=None):
    root=Path(root)if root else Path(__file__).resolve().parents[1];before={p:(root/p).read_bytes()for p in FILES};count=0
    def eq(a,b):
        nonlocal count
        if isinstance(b,dict):need(isinstance(a,dict)and set(a)==set(b),'dict keys');[eq(a[k],v)for k,v in b.items()]
        elif isinstance(b,list):need(isinstance(a,list)and len(a)==len(b),'list shape');[eq(x,y)for x,y in zip(a,b)]
        else:need(type(a)==type(b)and a==b,'comparison '+str((a,b)));count+=1
    review=json.loads(before[FILES[8]]);need(set(review['payload_bindings'])==set(FILES[:8]),'eight nonself bindings')
    for p,b in review['payload_bindings'].items():need(len(before[p])==b['bytes']and sha256(before[p]).hexdigest()==b['sha256'],'author freeze')
    manifest=json.loads(before[FILES[4]]);need(set(manifest['payloads'])==set(READERS)-{READERS[3]},'four reader bindings')
    for name,b in manifest['payloads'].items():raw=before['content/projects/'+name];need(len(raw)==b['bytes']and sha256(raw).hexdigest()==b['sha256'],'reader manifest')
    data=json.loads(before[FILES[1]]);expected=oracle(data);output=json.loads(before[FILES[3]]);eq(output,expected)
    namespace={'__name__':'v15_project_reader_checked','__file__':str(root/FILES[2])};stdout,stderr=io.StringIO(),io.StringIO();original=copy.deepcopy(data)
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):exec(compile(before[FILES[2]],str(root/FILES[2]),'exec'),namespace);actual=namespace['run'](data)
    need(not stdout.getvalue()and not stderr.getvalue(),'reader API quiet');eq(data,original);eq(actual,expected);json.dumps(actual,allow_nan=False)
    parser=Read();parser.feed(before[FILES[0]].decode());parser.close();need(not parser.stack and len(parser.ids)==len(set(parser.ids))and all(i=='project'or i.startswith('project-')for i in parser.ids),'IDs');need(parser.tasks==[f'project-task{i}'for i in range(1,8)]and parser.solutions==parser.tasks,'seven paired tasks');need(parser.rubrics=={k:20 for k in('evidence','feasibility','accounts','decision','transfer')},'five additive20 domains');need(set(parser.downloads)==set(READERS),'five flat download links');sources=json.loads(before[FILES[7]]);need(parser.sources=={s['id']:s['url']for s in sources['sources']},'source routes')
    records={r['id']:r for r in expected['policies']};one=records['K1F0S1A1'];two=records['K2F0S1A1'];sample=two['states'][0];threshold=records['K3F2S0A0'];ev=expected['evidence'];mins=min(rat(c)for r in records.values()if r['feasible']for st in r['states']for c in st['consumption'])
    displays={'project-population':[[g[k]for g in data['groups']]for k in('income','productivity_offset','damage_share','welfare_weight')],'project-technology':[data['technology'][k]for k in('capacity_cost','administration','travel','abatement_cost','emissions','abatement_reduction')]+[data['treasury']['reserve_limit']],'project-states':[s['weight']for s in expected['states']],'project-fit':[ev['identified_sum'],*ev['causal_interval'],ev['fits'][0]['holdout_prediction'],ev['wrong_slope_holdout_prediction'],ev['wrong_slope_holdout_error']],'project-threshold':[threshold['states'][0]['participants'],threshold['states'][2]['participants'],threshold['reserve'],threshold['states'][0]['refund'],threshold['states'][2]['refund']],'project-feasibility':[expected['policy_count'],expected['uniformly_feasible_count'],expected['policy_count']-expected['uniformly_feasible_count'],pack(mins)],'project-account':[two['reserve'],two['levy'],sample['participants'],sample['production'],sample['travel'],sample['emissions'],sample['damage_loss'],sample['real_public_cost'],two['action'][2]*sample['participants'],sample['expenses'],sample['fees'],sample['refund'],sample['resource_gain'],sample['weighted_gain']],'project-frontiers':[f['best']for f in expected['state_frontiers']],'project-expected-vector':[s['weighted_gain']for s in one['states']],'project-objectives':[expected['expected_weighted_optimum']['value'],one['expected_resource'],expected['expected_resource_optimum']['value'],two['expected_weighted']],'project-robust-regrets':two['regrets'],'project-regret-comparison':[records['K0F0S0A0']['max_regret'],one['max_regret'],two['max_regret']],'project-switches':[expected['forecast_envelope'][0]['q_interval'][1],expected['forecast_envelope'][1]['q_interval'][1],pack((sum(rat(t)*rat(p)for t,p in zip(data['uncertainty']['effects'],data['uncertainty']['effect_weights']))-1)/2)]}
    need(set(parser.markers)==set(displays),'all HTML numeric displays');[eq(literal(parser.markers[k]),v)for k,v in displays.items()]
    for row in records.values():
        if not row['feasible']:continue
        for state in row['states']:
            eq(pack(sum(map(rat,state['delta']))),state['resource_gain']);eq(pack(rat(row['reserve'])+rat(state['fees'])),pack(rat(state['expenses'])+rat(state['refund'])));need(all(rat(c)>=0 for c in state['consumption']),'consumption');eq(sum(state['admitted']),state['participants'])
    variants=[]
    low=copy.deepcopy(data);low['treasury']['reserve_limit']=8;variants.append(low)
    unequal=copy.deepcopy(data);unequal['groups'][0]['welfare_weight']=3;variants.append(unequal)
    poor=copy.deepcopy(data);poor['groups'][0]['income']=0;variants.append(poor)
    for variant in variants:
        own=oracle(variant);other=namespace['run'](variant);eq(other,own);need(any(not r['feasible']for r in other['policies']),'valid infeasible diagnostics')
    invalid=[]
    def malformed(path,value):
        d=copy.deepcopy(data);cursor=d
        for k in path[:-1]:cursor=cursor[k]
        cursor[path[-1]]=value;invalid.append(d)
    for path,value in[(('groups',0,'mass'),0),(('groups',0,'income'),-1),(('groups',0,'welfare_weight'),0),(('groups',0,'damage_share'),1),(('groups',0,'id'),'P2'),(('technology','travel'),True),(('technology','emissions'),float('nan')),(('technology','abatement_reduction'),2),(('menu','capacity'),[0,5]),(('menu','fee'),[0,0]),(('menu','subsidy'),[0,'1/2']),(('menu','abatement'),[0,2]),(('treasury','reserve_limit'),-1),(('uncertainty','effect_weights'),['1/2','1/2','1/2']),(('uncertainty','damage_weights'),[0,1]),(('uncertainty','effects'),[1,1,3]),(('evidence','selection_bound'),[3,1]),(('evidence','holdout_x'),0),(('conventions','participation'),'strict'),(('synthetic',),False)]:malformed(path,value)
    for bad in invalid:
        try:namespace['run'](bad)
        except(ValueError,TypeError,KeyError,ZeroDivisionError):pass
        else:raise ValueError('malformed accepted')
    cli_runs,alias_rejects=reader_cli(root,expected);need(all((root/p).read_bytes()==raw for p,raw in before.items()),'nine payloads mutated')
    return {'volume':'v15','component':'project','status':'pass','comparisons':count,'domain_rejections':len(invalid),'reader_cli_runs':cli_runs,'protected_alias_rejections':alias_rejects,'tasks':7,'rubric_domains':5,'policies':37,'uniformly_feasible':31,'states':6,'input_result_markers':len(displays),'runtime_files':9}
if __name__=='__main__':check()

"""Integer feasibility checks extracted from the separate MILP audit."""
import itertools

def ops(inp):return [o for job in inp['jobs'] for o in job]

def check(inp,sch):
    oo=ops(inp);x0=inp['x0'];t=inp['t'];errors=[]
    if set(sch)!=set(x0):return {'errors':['operation set']}
    for o in oo:
        k=o['id'];s=sch[k]['start']
        if type(s)!=int or s<0:errors.append([k,'integer start'])
        if sch[k]['machine']!=o['machine']:errors.append([k,'machine'])
        if x0[k]['start']<t:
            if sch[k]!=x0[k]:errors.append([k,'frozen'])
        elif s<t:errors.append([k,'past'])
        for br in inp['breakdowns']:
            if o['machine']==br['machine'] and s<br['end'] and s+o['duration']>br['start']:errors.append([k,'breakdown'])
    for job in inp['jobs']:
        for a,b in zip(job,job[1:]):
            if sch[a['id']]['start']+a['duration']>sch[b['id']]['start']:errors.append([a['id'],b['id'],'precedence'])
    for a,b in itertools.combinations(oo,2):
        if a['machine']==b['machine']:
            sa,sb=sch[a['id']]['start'],sch[b['id']]['start']
            if sa<sb+b['duration'] and sb<sa+a['duration']:errors.append([a['id'],b['id'],'overlap'])
    return dict(errors=errors,R=sum(sch[o['id']]['start']!=x0[o['id']]['start'] for o in oo if x0[o['id']]['start']>=t),M=max(sch[o['id']]['start']+o['duration'] for o in oo))

"""Deterministic measured findings. No semantic or causal generalizations."""
import copy, hashlib, json


def encoded(x): return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x): return hashlib.sha256(encoded(x).encode()).hexdigest()
def consequence(m):
    return {k:copy.deepcopy(m[k]) for k in ('valid','reward','revenue','tac','failed','unsolved_budget','sold','heat_integration') if k in m}


class Corpus:
    def __init__(self):
        self.groups={}; self.by_record={}
    def add(self, record, before_design, before_result):
        if not record.get('measured') or record.get('rejected'):return
        def fields(design):
            return {path:(dict(value) if isinstance(value,dict) else {str(i):v for i,v in enumerate(value)}) for path,value in design.items()}
        after=fields(record['design']); before=fields(before_design)
        changes=[]; context=copy.deepcopy(before)
        for path in sorted(set(before)|set(after)):
            if path not in before or path not in after:
                changes.append(dict(path=path,field='__column__',before=before.get(path),after=after.get(path)))
                context.pop(path,None)
            else:
                for field in sorted(set(before[path])|set(after[path])):
                    if before[path].get(field)!=after[path].get(field):
                        changes.append(dict(path=path,field=field,before=before[path].get(field),after=after[path].get(field)))
                        context[path].pop(field,None)
        # Repeated local changes share only when every unedited setting is exact.
        key=digest(dict(context=context,fields=[(c['path'],c['field']) for c in changes]))
        group=self.groups.setdefault(key,dict(id='finding-'+key,context=context,
            tested_fields=[dict(path=c['path'],field=c['field']) for c in changes],observations={},agents=[]))
        before_m=consequence(before_result or {});after_m=consequence(record['measured'])
        delta={k:after_m[k]-before_m[k] for k in ('reward','revenue','tac')
               if isinstance(before_m.get(k),(int,float)) and isinstance(after_m.get(k),(int,float))}
        observation=dict(changes=changes,before=before_m,after=after_m,delta=delta,
            exact_design_sha256=digest(after))
        oid=digest(observation)
        obs=group['observations'].setdefault(oid,{**observation,'support_ids':[]})
        obs['support_ids'].append(record['id'])
        if record['agent'] not in group['agents']:group['agents'].append(record['agent'])
        group['last_round']=record['round']
        # Opposing measured directions are retained, never averaged into a rule.
        signs={1 if o['delta']['reward']>0 else -1 if o['delta']['reward']<0 else 0
               for o in group['observations'].values() if 'reward' in o['delta']}
        group['mixed_reward_directions']=1 in signs and -1 in signs
        self.by_record[record['id']]=(key,oid)
    def candidates(self,agent,turn,records):
        # Fair first pass: a distinct finding last supported by each peer.
        peer_groups={}
        for key,g in self.groups.items():
            for a in g['agents']:
                if a!=agent:peer_groups.setdefault(a,[]).append(key)
        peers=sorted(peer_groups); offset=(turn-1)%len(peers) if peers else 0
        peers=peers[offset:]+peers[:offset];order=[]
        for a in peers:
            groups=peer_groups[a];key=groups[(turn-1)%len(groups)]
            if key not in order:order.append(key)
        rest=[key for key in self.groups if key not in order]
        offset=(turn-1)%len(rest) if rest else 0
        order+=rest[offset:]+rest[:offset]
        # Breadth first across findings before adding more observations from one.
        queues=[]
        for key in order:
            observations=list(self.groups[key]['observations'].values())
            offset=(turn-1)%len(observations)
            queues.append(observations[offset:]+observations[:offset])
        ids=[]
        for depth in range(max((len(q) for q in queues),default=0)):
            for q in queues:
                if depth<len(q):
                    rid=q[depth]['support_ids'][0]
                    if rid in records:ids.append(rid)
                    if len(ids)==20:return ids
        return ids
    def packet(self, selected):
        groups={}
        for rid,r in selected.items():
            if rid not in self.by_record:continue
            key,oid=self.by_record[rid];g=self.groups[key];o=g['observations'][oid]
            entry=groups.setdefault(key,dict(id=g['id'],applicability_context=g['context'],
                tested_fields=g['tested_fields'],mixed_reward_directions=g['mixed_reward_directions'],
                total_observations=len(g['observations']),observations={}))
            # Full streams remain in the audit; exact compact measured evidence appears here.
            entry['observations'].setdefault(oid,dict(changes=o['changes'],delta=o['delta'],
                measured=r['measured'],support_ids=[],total_supports=len(o['support_ids']),
                exact_design_sha256=o['exact_design_sha256']))['support_ids'].append(rid)
        return list(groups.values())

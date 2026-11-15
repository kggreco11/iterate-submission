from types import SimpleNamespace
from sepdesign.swarm_context import recall_query

def test_large_unicode_plant_query_stays_bounded_and_retains_context():
    env=SimpleNamespace(names=['éthanol','water','benzene'],design={'B'*i:(50,3,3,.04) for i in range(1,200)},last={'sold':[{'node':'B'*i,'value':0,'flows':[10,5,1]} for i in range(1,10)],'failed':['B'*i for i in range(1,6)]},score=lambda:1.5)
    q=recall_query(env,'swarm-test'+'x'*100)
    assert len(q.encode('utf-8'))<=768
    assert 'swarm-test' in q and 'Failed column settings' in q and 'éthanol' in q


def test_all_query_sections_saturated_stay_within_cap():
    env=SimpleNamespace(names=['é'*100]*3,design={'B'*i:('z'*500,) for i in range(1,200)},last={'failed':['B'*i for i in range(1,6)],'sold':[{'node':'B'*i,'value':0,'flows':[1,2,3]} for i in range(1,10)]},score=lambda:1)
    assert len(recall_query(env,'r'*100).encode())<=768

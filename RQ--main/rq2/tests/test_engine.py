import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from rq2 import apply_update,evaluate,read_scenarios,split_rows

class TestEngine(unittest.TestCase):
 def test_exception_and_general_rule(self):
  rule={'id':'R1','conditions':{'contamination_risk':True},'conclusion':'reject','scenario_id':None}
  self.assertEqual(evaluate([rule],'S1',{'contamination_risk':True}),'reject')
  self.assertEqual(evaluate([rule],'S1',{'contamination_risk':None}),'uncertain')
  extra={'id':'R2','conditions':{},'conclusion':'accept','scenario_id':'S1'}
  self.assertEqual(evaluate([rule,extra],'S1',{'contamination_risk':True}),'accept')
  self.assertEqual(evaluate([rule,extra],'S2',{'contamination_risk':True}),'reject')
 def test_b1_restriction(self):
  with self.assertRaises(ValueError):apply_update([],{'operation':'replace_rule','target_rule_ids':['R1'],'new_rules':[]},'B1')
 def test_b2_replace(self):
  existing=[{'id':'R1','conditions':{},'conclusion':'reject','scenario_id':None}]
  u={'operation':'replace_rule','target_rule_ids':['R1'],'new_rules':[{'conditions':{'authorized':False},'conclusion':'reject'}]}
  result=apply_update(existing,u,'B2');self.assertEqual(len(result),1)
  self.assertEqual(result[0]['conditions'],{'authorized':False})
 def test_split(self):
  rows=read_scenarios(str(Path(__file__).resolve().parents[1]/'data/current_dataset.json'))
  self.assertEqual(len(rows),120)
  a,b=split_rows(rows,17)
  self.assertFalse({r['id'] for r in a}&{r['id'] for r in b})
  self.assertEqual(len(a)+len(b),120)
 def test_forbidden_predicate(self):
  with self.assertRaises(ValueError):apply_update([],{'operation':'add_rule','target_rule_ids':[], 'new_rules':[{'conditions':{'hallucinated':True},'conclusion':'reject'}]},'B1')

if __name__=='__main__':unittest.main()

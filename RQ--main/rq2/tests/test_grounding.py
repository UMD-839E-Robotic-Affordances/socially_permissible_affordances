import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from rq2 import ground, PREDICATES
class Mock:
 def __init__(self,d):self.d=d
 def json(self,*args):return self.d
class TestGrounding(unittest.TestCase):
 def test_flat(self):
  g=ground(Mock({'authorized': True,'food_contact_object':'false'}),{'context':'x','goal':'y','action':'z'})
  self.assertIs(g['authorized'],True);self.assertIs(g['food_contact_object'],False)
 def test_nested(self):
  g=ground(Mock({'predicates':{'authorized':'false'}}),{'context':'x','goal':'y','action':'z'})
  self.assertIs(g['authorized'],False)
 def test_invalid_schema(self):
  with self.assertRaises(ValueError):ground(Mock({'result':{'x':True}}),{'context':'x','goal':'y','action':'z'})

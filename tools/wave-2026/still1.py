import sys, os, importlib.util
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('edl', R + '/60_cut/' + os.environ.get('EDL', 'edl.py')); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
import eng
for t in sys.argv[1:]:
    eng.frame(E.SHOTS, E.EV, float(t)).save(R + f'/review/f_{t}.jpg', quality=90)

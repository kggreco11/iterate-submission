$ErrorActionPreference='Stop'
$Code = @'
import json,gzip,base64
from pathlib import Path
p=Path(r'C:\iterate-hackathon\hc12-qualification\results\hc12-qualification')
d={'report':json.loads((p/'report.json').read_text()),'calls':json.loads((p/'calls.json').read_text())}
b=base64.b64encode(gzip.compress(json.dumps(d,separators=(',',':')).encode())).decode()
(p/'transfer.txt').write_text(b)
print(json.dumps({'length':len(b),'chunk':b[:3500]}))
'@
& 'C:\chemsep-benchmark\venv\Scripts\python.exe' -c $Code
